"""Run the scheduled article generator with a data-driven topic priority.

Pinterest delivery retries must not block the next scheduled article. The priority
list below lets current Search Console / Pinterest signals move a few existing
pending topics ahead of the general backlog without deleting or rewriting the
queue.

A same-day guard prevents a manual test/retry plus the scheduled Cron from
creating two articles on the same UTC day and wasting Gemini quota. When an
article was already published today, the runner exits successfully so the outer
Cloudflare agent can continue with pending Pinterest delivery.
"""

import datetime

import generate_post


PRIORITY_TOPIC_TITLES = [
    "How to Propagate Thai Constellation Monstera Successfully",
    "Common Mistakes When Repotting Rare Aroids",
    "Dealing With Thrips and Mites on Rare Plants Without Harming Variegation",
]


def prioritized_load_queue():
    """Keep completed history intact and order pending topics by current demand."""
    queue = original_load_queue()
    topics = queue.get("topics", [])
    completed = [item for item in topics if item.get("status") != "pending"]
    pending = [item for item in topics if item.get("status") == "pending"]

    rank = {title: index for index, title in enumerate(PRIORITY_TOPIC_TITLES)}
    pending = sorted(
        enumerate(pending),
        key=lambda pair: (rank.get(pair[1].get("title"), len(rank)), pair[0]),
    )
    queue["topics"] = completed + [item for _, item in pending]
    return queue


original_load_queue = generate_post.load_queue


def article_already_published_today(queue):
    """Return True when this queue already contains an article published today."""
    today = datetime.date.today().isoformat()
    return any(
        item.get("status") != "pending" and item.get("published_date") == today
        for item in queue.get("topics", [])
    )


def main():
    # A Deploy Hook test/retry can happen shortly before the scheduled Cron. Do
    # not spend Gemini quota generating another article on the same UTC day.
    current_queue = original_load_queue()
    if article_already_published_today(current_queue):
        print("Articolo già pubblicato oggi: salto Gemini e continuo con i Pin pending.")
        return

    # Pinterest delivery is retried later by the workflow. An older pending Pin
    # must not block the next scheduled article on a future publishing day.
    generate_post.has_pending_pin = lambda queue: False
    generate_post.load_queue = prioritized_load_queue
    generate_post.main()


if __name__ == "__main__":
    main()
