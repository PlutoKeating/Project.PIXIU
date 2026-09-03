"""openKylin Agent integration package.

The actual plugin lives in :mod:`integrations.kylin_agent.pixiu` and is loaded
by the Agent host.  Keeping this namespace import-free also lets packaging and
static checks run on systems where the optional Agent runtime is absent.
"""
