import os
import subprocess
import sys
from pathlib import Path

# Configuration defaults
BASE_DIR = Path("/home/jayson_tolleson/Cascade")
STORAGE_DIR = BASE_DIR / "projects"
VENV_DIR = BASE_DIR / "venv"

def run_command(cmd, cwd=None):
    print(f"[RUNNING] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"[ERROR] Command failed: {result.stderr.strip()}")
        sys.exit(result.returncode)
    if result.stdout.strip():
        print(result.stdout.strip())

def setup_environment():
    print("========================================")
    print("    CASCADE-CAD DEPLOYMENT INSTALLER    ")
    print("========================================")

    # 1. Ensure storage and workspace directories exist
    print("\n[1/5] Setting up directory structure...")
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[SUCCESS] Storage directory verified at: {STORAGE_DIR}")

    # 2. Check / Setup Python Virtual Environment
    print("\n[2/5] Checking Python virtual environment...")
    if not VENV_DIR.exists():
        run_command([sys.executable, "-m", "venv", str(VENV_DIR)])
        print(f"[SUCCESS] Created virtual environment at: {VENV_DIR}")
    else:
        print(f"[SUCCESS] Virtual environment already exists at: {VENV_DIR}")

    # Determine pip path inside venv
    pip_path = VENV_DIR / "bin" / "pip"

    # 3. Install/Upgrade Dependencies
    print("\n[3/5] Installing core dependencies (Quart, Quart-CORS, etc.)...")
    run_command([str(pip_path), "install", "--upgrade", "pip"])
    if Path("requirements.txt").exists():
        run_command([str(pip_path), "install", "-r", "requirements.txt"])
    else:
        # Fallback core packages if requirements.txt isn't present yet
        run_command([str(pip_path), "install", "quart", "quart-cors", "trimesh", "numpy"])

    # 4. Set Environment Variables Profile
    print("\n[4/5] Configuring environment profile...")
    env_profile = BASE_DIR / ".env"
    env_content = f"CASCADE_STORAGE_DIR={STORAGE_DIR}\nPORT=5000\n"
    env_profile.write_text(env_content, encoding="utf-8")
    print(f"[SUCCESS] Written environment config to: {env_profile}")

    # 5. Git repository sync check
    print("\n[5/5] Verifying Git status...")
    if Path(".git").exists():
        run_command(["git", "status"])
    else:
        print("[INFO] Not a git repository or git not initialized yet.")

    print("\n========================================")
    print("      INSTALLATION COMPLETED CLEANLY    ")
    print("========================================")
    print(f"To start your server, run:")
    print(f"source {VENV_DIR}/bin/activate && export CASCADE_STORAGE_DIR={STORAGE_DIR} && python3 -m webcad_xbf.app")

if __name__ == "__main__":
    setup_environment()
