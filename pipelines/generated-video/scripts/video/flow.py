"""Compatibility import for the single maintained Flow implementation."""
import sys
from scripts import flow_video as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
