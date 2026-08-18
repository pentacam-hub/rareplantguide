"""Run the daily article generator without letting a Pinterest backlog block content.

The normal generator keeps its conservative standalone behavior, but the scheduled
content workflow must publish one article per day even if an older Pinterest Pin
is still waiting to be retried.
"""

import generate_post


def main():
    # Pinterest delivery is retried later by the workflow. It must never stop the
    # independent daily article cadence.
    generate_post.has_pending_pin = lambda queue: False
    generate_post.main()


if __name__ == "__main__":
    main()
