PYTHON ?= python3
PYTHONPATH := src
FIXED_NOW := 2026-07-28T12:00:00Z

.PHONY: help test check demo incident lineage clean

help:
	@echo "Targets:"
	@echo "  test      Run the offline unit test suite"
	@echo "  check     Compile source and run tests"
	@echo "  demo      Evaluate the healthy synthetic dataset"
	@echo "  incident  Evaluate the synthetic incident without failing Make"
	@echo "  lineage   Inspect transitive lineage for the contracted dataset"

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -v

check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m compileall -q src tests
	$(MAKE) test

demo:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m data_observer run \
		--contract contracts/orders.contract.json \
		--data data/orders_healthy.csv \
		--lineage lineage/manifest.json \
		--output-dir .artifacts/healthy \
		--now $(FIXED_NOW)

incident:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m data_observer run \
		--contract contracts/orders.contract.json \
		--data data/orders_incident.csv \
		--lineage lineage/manifest.json \
		--output-dir .artifacts/incident \
		--now $(FIXED_NOW) \
		--fail-on never

lineage:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m data_observer lineage \
		--manifest lineage/manifest.json \
		--asset silver.orders_clean

clean:
	rm -rf .artifacts
