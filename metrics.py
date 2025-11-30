"""
Handles loading, saving, and reporting metrics.
"""
import config
import utils
import logging

def load_metrics():
    """Load the metrics file."""
    default_metrics = {
        "total_runs": 0,
        "total_cost_usd": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }
    return utils.load_json_file(config.METRICS_PATH, default_metrics)

def update_and_report_metrics(metrics_data, input_tokens=0, output_tokens=0):
    """
    Updates metrics with new data, calculates costs,
    prints a report, and returns the updated data.
    """
    run_cost = (input_tokens * config.INPUT_TOKEN_PRICE_USD) + \
               (output_tokens * config.OUTPUT_TOKEN_PRICE_USD)

    metrics_data["total_runs"] += 1
    metrics_data["total_cost_usd"] += run_cost
    metrics_data["total_input_tokens"] += input_tokens
    metrics_data["total_output_tokens"] += output_tokens

    avg_cost = metrics_data["total_cost_usd"] / metrics_data["total_runs"]
    
    logging.info(f"[Metrics] Run Cost: ${run_cost:.8f} | Total Cost: ${metrics_data['total_cost_usd']:.8f} | Avg Cost: ${avg_cost:.8f}")
    
    return metrics_data

