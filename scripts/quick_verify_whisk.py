import sys
import os
import inspect

# Add project root to path
sys.path.append(os.getcwd())

try:
    print("🔍 Attempting to import WhiskAgent...")
    from packages.services.whisk_agent import WhiskAgent
    print("✅ WhiskAgent imported successfully (Syntax is valid).")
    
    # Check signature of generate_batch
    sig = inspect.signature(WhiskAgent.generate_batch)
    print(f"ℹ️  generate_batch signature: {sig}")
    
    if 'style_paths' in sig.parameters:
        print("❌ FAILED: 'style_paths' parameter is still present in generate_batch!")
        sys.exit(1)
    else:
        print("✅ SUCCESS: 'style_paths' parameter correctly removed.")
        
    print("🚀 Verification Passed.")
    sys.exit(0)

except SyntaxError as e:
    print(f"❌ SyntaxError: {e}")
    print(f"   File: {e.filename}, Line: {e.lineno}")
    sys.exit(1)
except IndentationError as e:
    print(f"❌ IndentationError: {e}")
    print(f"   File: {e.filename}, Line: {e.lineno}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    sys.exit(1)
