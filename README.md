# QUIC Case Study

---

# Overview

This project demonstrates a complete local implementation of QUIC and HTTP/3 using the aioquic framework. It includes a working QUIC-based HTTP/3 server, multiple client programs, benchmarking tools, migration tests, packet-loss experiments, and comparison scripts that evaluate the performance of QUIC against the traditional TCP (HTTP/1.1) protocol.

The goal of this work is to analyze how QUIC behaves under different network conditions, observe the benefits of multiplexing and connection migration, and quantify the performance difference between QUIC and TCP using repeatable, code-driven experiments.

---

# Project Structure

## 1. QUIC/HTTP3 Server

### h3_server.py

A full HTTP/3 server built on aioquic. It:

* Listens on port 4433
* Performs QUIC handshake
* Interprets HTTP/3 GET requests
* Serves files from the `www/` directory
* Responds using HTTP/3 headers and data frames
* Handles client errors cleanly

---

## 2. QUIC Clients

### h3_client.py

Sends multiple concurrent HTTP/3 GET requests over a single QUIC connection.
Demonstrates stream multiplexing and measures per-stream latency.

### h3_client_stress.py

Issues 50 simultaneous GET requests to evaluate QUIC’s high concurrency behavior.
Tracks how long all 50 streams take to finish inside one QUIC session.

### h3_client_migration.py

Performs a large download, then triggers a QUIC Connection ID migration mid-transfer.
Shows QUIC’s ability to continue transmission seamlessly after a simulated network change.

---

## 3. TCP Server and TCP Tests

### tcp_server.py

HTTPS (HTTP/1.1) server using aiohttp.
Used as a baseline for comparison with QUIC.

### tcp_migration_test.py

Downloads a large file and forcibly closes the TCP socket mid-download to simulate a network switch.
Demonstrates that TCP cannot migrate or continue the transfer after a connection break.

### tcp_stress_test.py

Sequentially downloads 50 files using TCP over HTTPS.
Used to compare total transfer time with QUIC’s multiplexed streams.

---

## 4. Benchmarking Tools

### benchmark.py

Runs repeated QUIC and TCP latency tests for the same resource.
Outputs:

* Per-trial latency results
* A CSV file
* A latency comparison plot
* Average QUIC vs TCP latency numbers

### benchmark_loss.py

Simulates packet loss using Linux `tc netem`.
Runs QUIC and TCP tests at different loss percentages.
Outputs:

* CSV file
* Packet loss plot
* Comparison of QUIC vs TCP degradation under loss

---

## 5. Summary Visualization

### comparison_summary.py

Combines benchmark results and generates:

* Baseline latency comparison chart
* Packet-loss impact chart
* Multiplexing time comparison chart
* Printed summary of all results

---

## 6. Helper Tool

### combine.py

Collects all Python files in the project and compiles them into a single text file for documentation and submission purposes.

---

# Explanation of Output Images

## comparison_baseline.png

Shows the average latency of QUIC versus TCP for identical requests over multiple trials.
QUIC appears faster due to:

* Reduced handshake cost
* Lack of head-of-line blocking
* Stream-level granularity

TCP latencies are higher due to handshake delays and sequential data delivery constraints.

---

## comparison_loss.png

Displays how QUIC and TCP respond to increasing packet loss.
QUIC maintains more stable latency because retransmissions occur per-stream rather than blocking the entire connection.
TCP performance deteriorates rapidly under loss due to head-of-line blocking and connection-wide congestion handling.

---

## comparison_multiplex.png

Shows the total time required to download 50 files using QUIC vs TCP.
QUIC uses a single connection with 50 parallel streams, demonstrating efficient multiplexing.
TCP must open 50 separate connections, resulting in higher total time and repeated handshake overhead.

---

## latency_comparison.png

Presents a boxplot of latency distributions for QUIC and TCP over multiple runs.
QUIC typically shows a tighter spread and lower median latency.
TCP shows more variability and higher medians.

---

## loss_impact.png

Generated from packet-loss experiments, this plot compares latency at several loss percentages.
QUIC degrades more gracefully under adverse network conditions.
TCP latency rises significantly due to cumulative retransmission delays.

---

# Author

Syed Abubaker Ahmed

AI/ML Engineer | Computer Vision Developer | Autonomous Systems & Smart Mobility | Smart City Technology Researcher | CS Undergraduate
