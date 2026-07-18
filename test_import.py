import sys
try:
    from packages.api.app import app
    print("Import successful!")
except Exception as e:
    import traceback
    traceback.print_exc()
