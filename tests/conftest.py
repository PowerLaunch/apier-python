"""Pytest fixtures — all tests run OFFLINE.

The real network is never touched: every test that exercises Client._request
patches the OpenerDirector returned by build_opener() with a fake opener
whose .open() returns a pre-canned response. Rule R10.
"""
