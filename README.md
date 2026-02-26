# Lera-KI Build & Run


### Note: KI_testing is for our demo (for both VCs and the small subset of teachers) running on the flask engine, not intended for realtime production

### 1. Setup Environment
git clone <repo-url>
cd Lera-KI
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

### 2. Configuration

Drop the .env file I provided you directly into the KI_testing/ folder.

### 3. Execution
cd KI_testing
python app.py

### 4. Access

Desktop: http://localhost:5000
Mobile (for Camera Grading): http://<YOUR_HOST_IP>:5000 (Must be on the same Wi-Fi. If it times out on Linux, run sudo ufw allow 5000, or allow port 5000 through firewall).