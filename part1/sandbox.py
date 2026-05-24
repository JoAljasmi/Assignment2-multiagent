
import subprocess


CONTAINER_NAME = "agent-sandbox"
TIMEOUT_SECONDS = 30


def run_bash(command):
    answer = input(f"Run {command}? (y/n): ")
    if answer.lower() != "y":
        return "[user denied command execution]"      
    
    #using docker to run the command
    try:
          
        result = subprocess.run(
            ["docker", "exec", CONTAINER_NAME, "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        #returning readable outputs
        return (
        f"[exit code: {result.returncode}]\n"
        f"[stdout]\n{result.stdout}\n"
        f"[stderr]\n{result.stderr}"
        )
    except subprocess.TimeoutExpired:
        return f"[error: command timed out after {TIMEOUT_SECONDS} seconds]"


if __name__ == "__main__":
    output = run_bash("ls /")
    print(output)