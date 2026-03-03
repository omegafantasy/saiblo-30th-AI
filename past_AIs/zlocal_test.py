import os
import subprocess
from multiprocessing import Pool
import json
from tqdm import tqdm


make = True  # No need for quotes around boolean values
pac_path = "pac.exe"  # Relative paths are risky, see below
ghost_path = "ghost.exe"
num_rounds = 15  # Changed 'round' to 'num_rounds' (avoid shadowing built-in)
num_bigrounds = 5


def run_zlocal(idx):
    # Use subprocess.run to suppress output
    command = ["python", "zlocal.py", "--dir_pacman", pac_path, "--dir_ghosts", ghost_path, "--idx", str(idx)]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":  # Crucial for Windows multiprocessing
    if make:
        os.system("make")
    total_scores = [0, 0]
    for i in tqdm(range(num_bigrounds)):
        with Pool(num_rounds) as p:
            results = p.map(run_zlocal, range(num_rounds))
        p.join()
        for i in range(num_rounds):
            with open(f"replay/replay{i}.json", "r") as f:
                lines = f.readlines()
                last_line = json.loads(lines[-1])
                score = last_line["score"]
                total_scores[0] += int(score[0])
                total_scores[1] += int(score[1])
                print(f"Match {i}: {score}")
    print(f"Total scores: {total_scores}")
