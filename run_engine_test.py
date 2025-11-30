"""
TrueBrief Engine v2 Test Runner

This is the main "app" that:

1. Asks for a topic.
2. Checks if the topic exists in 'topics.json'.
3. If NO, runs the 'onboarding.py' pipeline to create it.
4. If YES, runs the 'engine.py' (Golden Pipeline) to get updates.
"""

import logging
import time
import os
import engine
import metrics
import config
import utils
import onboarding

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    logging.info("--- Starting TrueBrief Engine v2 ---")

    # 1. LOAD TOPICS DATABASE
    topics_db = utils.load_json_file(config.TOPICS_DB_PATH, default_data={})

    # 2. GET USER INPUT
    print("\nAvailable Topics:")
    for topic_id in topics_db:
        print(f"- {topic_id}")

    user_input = input("\nEnter a topic ID from the list above, or type a new topic to onboard: ")
    if not user_input:
        logging.error("No input provided. Exiting.")
        return

    # Create a simple, reusable ID from the topic
    TOPIC_ID = user_input.lower().replace(" ", "_").replace("'", "").replace('"', "")[:25]
    USER_ID = "test_user_001" # This would be dynamic in a real app

    # 3. DECIDE WHICH PIPELINE TO RUN
    topic_config = topics_db.get(TOPIC_ID)

    if not topic_config:
        # --- NEW TOPIC FLOW ---
        logging.info(f"Topic ID '{TOPIC_ID}' not found. Starting ONE-TIME Topic Onboarding...")
        # We pass the user's *original text* to the onboarding LLM
        topic_config = onboarding.onboard_new_topic(user_input, TOPIC_ID)

        if not topic_config:
            logging.error(f"Failed to onboard new topic '{user_input}'. Exiting.")
            return

        logging.info(f"New topic '{TOPIC_ID}' created successfully! Running first update...")
        last_update_timestamp = 0 # It's a new topic

    else:
        # --- EXISTING TOPIC FLOW ---
        logging.info(f"Found existing topic '{TOPIC_ID}'.")
        timestamp_file = os.path.join(config.DATA_DIR, f"{USER_ID}_{TOPIC_ID}_timestamp.txt")
        try:
            with open(timestamp_file, 'r') as f:
                last_update_timestamp = float(f.read())
        except Exception:
            last_update_timestamp = 0 # First run for this user

    # --- 4. RUN THE "GOLDEN PIPELINE" (engine.py) ---
    USER_TOPIC_STRING = topic_config["user_topic_string"]
    TOPIC_FEED_URLS = topic_config["feeds"]
    fact_ledger_path = config.FACT_LEDGER_PATH_TEMPLATE.format(user_id=USER_ID, topic_id=TOPIC_ID)

    logging.info(f"Running for user '{USER_ID}' on topic '{TOPIC_ID}' ('{USER_TOPIC_STRING}').")
    logging.info(f"Last update was at timestamp: {last_update_timestamp}")

    result = engine.run_engine_cycle(
        feed_urls=TOPIC_FEED_URLS,
        fact_ledger_path=fact_ledger_path,
        user_topic_string=USER_TOPIC_STRING,
        last_update_timestamp=last_update_timestamp
    )

    if not result:
        logging.error("Engine run failed.")
        return

    # --- 5. PROCESS & DISPLAY RESULTS ---
    summary = result["summary_json"]
    metrics_path = config.METRICS_PATH
    metrics_data = metrics.load_metrics()

    print("\n" + "=" * 60)
    print(f"--- Generated Summary for {TOPIC_ID} ---")
    print("=" * 60)
    print(summary["summary_text"])
    print("\n--- Sources Used ---")
    if summary["sources_used"]:
        for source in summary["sources_used"]:
            print(f"  - [{source['source_name']} ({source['domain']})]({source['url']})")
    else:
        print("  (No sources cited)")
    print("=" * 60)

    # --- 6. UPDATE METRICS & TIMESTAMP ---
    metrics_data = metrics.update_and_report_metrics(
        metrics_data,
        result["llm_input_tokens"],
        result["llm_output_tokens"]
    )
    utils.save_json_file(metrics_path, metrics_data)

    # Save new timestamp
    timestamp_file = os.path.join(config.DATA_DIR, f"{USER_ID}_{TOPIC_ID}_timestamp.txt")
    with open(timestamp_file, 'w') as f:
        f.write(str(time.time()))
    logging.info(f"Updated timestamp to {time.time()}")

    logging.info("--- TrueBrief Engine v2 Test Run Finished ---")


if __name__ == "__main__":
    main()
