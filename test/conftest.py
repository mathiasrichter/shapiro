def pytest_addoption(parser):
    parser.addoption("--github_token", action="store", default=None, help="TheGithub token with read access to the Shapiro repo for running the tests for the Github content adaptor. If no token is passed on the command line, then the content adaptor tests will not be run (warnings are issued).")
