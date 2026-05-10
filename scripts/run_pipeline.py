import os
import sys
import argparse
import logging
from truebrief.pipeline.runner import PipelineRunner

def main():
    parser = argparse.ArgumentParser(description="Run the TrueBrief Pipeline manually.")
    parser.add_argument("topic", type=str, help="The topic to track (e.g., 'TSMC semiconductor')")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.debug else logging.INFO
    
    # We must explicitly set encoding for Windows terminals to avoid charmap errors with emojis
    # Note: this affects the stream handler but not print directly, so we just encode safely.
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    runner = PipelineRunner()
    
    try:
        brief = runner.run(args.topic)
        print("\n" + "="*50 + "\n")
        # Safe print for Windows terminal to avoid UnicodeEncodeError with emojis
        print(brief.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        print("\n" + "="*50 + "\n")
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
