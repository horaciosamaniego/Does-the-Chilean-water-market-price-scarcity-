.PHONY: all setup model projection figure clean

all: model projection figure

setup:
	pip install -r requirements.txt

model:
	python src/wr_spatial_corrected.py | tee output/model.txt

projection:
	python src/wr_projection.py | tee output/projection.txt

figure:
	python src/make_figure.py

clean:
	rm -f output/*.txt
	find . -name __pycache__ -type d -exec rm -rf {} +
