# TrueBrief - Week 1 MVP Pipeline

This is the core pipeline proof-of-concept for TrueBrief, designed to test the novelty detection and summarization flow.

## Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Google Gemini API:**
   - Get your API key from https://aistudio.google.com/app/apikey
   - Create a `.env` file in the root directory:
     ```
     GEMINI_API_KEY=your_api_key_here
     ```

3. **Run the pipeline:**
   ```bash
   python pipeline.py
   ```

## What This Does

The pipeline will:
1. Fetch articles from RSS feeds for a hardcoded topic
2. Break articles into sentences and generate embeddings
3. Compare against a simple fact history to find new information
4. Summarize only the novel facts using Gemini API
5. Print the result

## File Structure

- `pipeline.py` - Main pipeline script
- `rss_fetcher.py` - RSS feed fetching module
- `novelty_detector.py` - Embedding and novelty detection logic
- `summarizer.py` - Gemini API summarization
- `fact_history.txt` - Simple text-based fact history (for MVP)



