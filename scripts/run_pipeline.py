import os
import sys
import argparse
import logging
from truebrief.pipeline.runner import PipelineRunner

def main():
    parser = argparse.ArgumentParser(description="Run the TrueBrief Pipeline manually.")
    parser.add_argument("topic", type=str, help="The topic to track (e.g., 'TSMC semiconductor')")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--topic-id", type=str, default=None,
        help="Existing topics.id to scope facts to. If omitted, a topic row matching "
             "--topic by raw_query is reused if one exists, otherwise a new one is created.",
    )
    parser.add_argument(
        "--no-persist", action="store_true",
        help="Don't touch the DB at all: monkeypatches VectorStore.add_fact() to a no-op "
             "so this stays a pure read-only smoke test.",
    )

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.debug else logging.INFO

    # We must explicitly set encoding for Windows terminals to avoid charmap errors with emojis
    # Note: this affects the stream handler but not print directly, so we just encode safely.
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 2026-08-13: this script used to call runner.run(args.topic) with NO topic_id.
    # PipelineRunner.run()'s topic_id defaults to None and threads straight through to
    # VectorStore.add_fact(), which used to insert real known_facts rows with
    # topic_id=NULL — a live-DB audit found 675 of these (2026-06-08 to 2026-08-13),
    # unrecoverable since find_similar() is always topic-scoped, so they can never be
    # deduped. add_fact() now raises loudly on a missing topic_id instead of silently
    # accepting one; this script resolves (or creates) a real topic row up front so a
    # manual run keeps working without corrupting production data.
    if args.no_persist:
        from truebrief.ledger.vector_store import VectorStore
        VectorStore.add_fact = lambda self, alpha, story_node_id=None: alpha
        topic_id = None
        logging.info("--no-persist: add_fact() is a no-op, nothing will be written to the DB.")
    else:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()
        if args.topic_id:
            topic_id = args.topic_id
        else:
            existing = db.table("topics").select("id").eq("raw_query", args.topic).limit(1).execute()
            if existing.data:
                topic_id = existing.data[0]["id"]
                logging.info(f"Reusing existing topic row for '{args.topic}' (id={topic_id}).")
            else:
                created = db.table("topics").insert({"raw_query": args.topic}).execute()
                topic_id = created.data[0]["id"]
                logging.info(f"Created new topic row for '{args.topic}' (id={topic_id}).")

    runner = PipelineRunner()

    try:
        brief = runner.run(args.topic, topic_id=topic_id)
        print("\n" + "="*50 + "\n")
        # Safe print for Windows terminal to avoid UnicodeEncodeError with emojis
        print(brief.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        print("\n" + "="*50 + "\n")
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
