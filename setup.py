"""
Setup script for debate claim extraction package
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="debate-claim-extractor",
    version="0.1.0",
    description="Extract factual claims from debate transcripts",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="debate-check",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "spacy>=3.7.0",
        "pydantic>=2.0.0", 
        "click>=8.0.0",
        "pyyaml>=6.0.0",
        "python-dateutil>=2.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "debate-claim-extractor=debate_claim_extractor.__main__:main",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
