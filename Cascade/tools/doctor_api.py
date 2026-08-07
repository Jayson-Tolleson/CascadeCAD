from pathlib import Path
import re

from tools.doctor_common import ROOT


ROUTE_PATTERNS = [
    r'@app\.route\(["\'](.*?)["\']',
    r'@app\.get\(["\'](.*?)["\']',
    r'@app\.post\(["\'](.*?)["\']',
    r'@app\.put\(["\'](.*?)["\']',
    r'@app\.delete\(["\'](.*?)["\']',
]


def find_api_routes():

    routes = []

    for path in ROOT.rglob("*.py"):

        if "venv" in path.parts:
            continue

        try:
            text = path.read_text(errors="ignore")

        except Exception:
            continue


        for pattern in ROUTE_PATTERNS:

            matches = re.findall(pattern, text)

            for route in matches:

                routes.append({
                    "route": route,
                    "file": str(path.relative_to(ROOT))
                })


    return routes



def report():

    routes = find_api_routes()

    result = {
        "count": len(routes),
        "routes": routes
    }

    print()
    print("API Routes")
    print("----------------")

    for item in routes:
        print(
            f"{item['route']}  ->  {item['file']}"
        )


    return result



if __name__ == "__main__":
    report()
