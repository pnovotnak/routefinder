.venv:
	poetry env use -- $$(which python3)

.venv-install-dev:
	. .venv/bin/activate
	poetry install --with dev

local-env: .venv .venv-install-dev


