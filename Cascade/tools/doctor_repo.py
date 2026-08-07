from tools.doctor_common import ROOT, find_files


def report():

    js = find_files(ROOT, ".js")
    py = find_files(ROOT, ".py")
    html = find_files(ROOT, ".html")

    result = {
        "javascript": len(js),
        "python": len(py),
        "html": len(html),
    }

    print()
    print("Repository")
    print("----------------")
    print(f"JavaScript Files : {result['javascript']}")
    print(f"Python Files     : {result['python']}")
    print(f"HTML Templates   : {result['html']}")

    return result


if __name__ == "__main__":
    report()
