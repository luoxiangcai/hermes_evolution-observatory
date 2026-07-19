.PHONY: install run dev test clean

install:
	pip install -r requirements.txt

run:
	cd backend && python main.py

dev:
	cd backend && uvicorn main:app --reload --host 127.0.0.1 --port 9120

test:
	pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
