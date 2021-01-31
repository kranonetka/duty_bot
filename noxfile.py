import nox
from nox import sessions


@nox.session
def lint(session: sessions.Session):
    session.install('flake8')
    session.run('flake8', '--exclude=.nox/', '.')
