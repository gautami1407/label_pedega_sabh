from lps.gateway.main import app

def format_route(route):
    methods = ",".join(sorted(route.methods))
    return f"{methods} {route.path}"

if __name__ == "__main__":
    for r in app.routes:
        print(format_route(r))
