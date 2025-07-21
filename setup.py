from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="foxess-mcp-server",
    version="0.1.0",
    author="FoxESS MCP Community",
    author_email="community@foxess-mcp.org",
    description="MCP Server for FoxESS Solar Inverters - AI access to solar energy data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/holger1411/foxess-mcp-server",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Topic :: Home Automation",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0", 
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
            "flake8>=6.0.0"
        ],
        "analytics": [
            "numpy>=1.24.0",
            "pandas>=2.0.0"
        ]
    },
    entry_points={
        "console_scripts": [
            "foxess-mcp-server=foxess_mcp_server.server:main",
        ],
    },
    include_package_data=True,
    package_data={
        "foxess_mcp_server": ["config/*.json"],
    },
    keywords=["mcp", "foxess", "solar", "inverter", "energy", "claude", "ai"],
    project_urls={
        "Bug Reports": "https://github.com/holger1411/foxess-mcp-server/issues",
        "Source": "https://github.com/holger1411/foxess-mcp-server",
        "Documentation": "https://github.com/holger1411/foxess-mcp-server/wiki",
    },
)
