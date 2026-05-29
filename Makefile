.PHONY: test demo web check-nebius run-actions train rasa

test:
	python3 -m unittest discover -s tests

demo:
	python3 -m auction_agent.cli analyze

web:
	python3 -m auction_agent.web

check-nebius:
	python3 scripts/check_nebius.py

run-actions:
	rasa run actions

train:
	rasa train

rasa:
	rasa run --enable-api --cors "*"
