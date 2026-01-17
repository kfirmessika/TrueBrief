from setuptools import setup, find_packages

setup(
    name="truebrief",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastembed",
        "numpy",
        "scikit-learn",
        "spacy",
        "feedparser",
        "crawl4ai",
        "xgboost",
        "qdrant-client",
        "google-generativeai",
        "python-dotenv",
        "playwright",
    ],
)
