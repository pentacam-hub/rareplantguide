"""Run the scheduled article generator with a data-driven topic priority.

Pinterest delivery retries must not block the next article. The priority list below
lets current Search Console / Pinterest signals move a few existing pending topics
ahead of the general backlog without deleting or rewriting the queue.
"""

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


def main():
    # Pinterest delivery is retried later by the workflow. It must never stop the
    # independent article cadence.
    generate_post.has_pending_pin = lambda queue: False
    generate_post.load_queue = prioritized_load_queue
    generate_post.main()


if __name__ == "__main__":
    main()
