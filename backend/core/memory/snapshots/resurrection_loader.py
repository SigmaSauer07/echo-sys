import argparse, requests, json

MCP_URL = "http://localhost:8050"

def load_resurrection(file=None, cid=None):
    if file:
        with open(file, 'r') as f:
            data = json.load(f)
    elif cid:
        # Placeholder: fetch from IPFS
        data = {"cid": cid, "note": "Fetched from IPFS"}
    else:
        print("Provide --file or --cid")
        return

    resp = requests.post(f"{MCP_URL}/load_memory", json=data)
    print("Response:", resp.status_code, resp.text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path to resurrection JSON")
    parser.add_argument("--cid", help="IPFS CID of resurrection memory")
    args = parser.parse_args()
    load_resurrection(file=args.file, cid=args.cid)
