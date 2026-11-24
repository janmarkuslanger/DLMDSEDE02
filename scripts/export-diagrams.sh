#!/bin/sh
# Exports the C4 views from architecture.dsl to PNG (diagram + legend per view) in out/.
set -eu
cd "$(dirname "$0")/.."

mkdir -p out
docker run --rm -v "$PWD":/usr/local/structurizr structurizr/structurizr \
  export -workspace architecture.dsl -format plantuml/structurizr -output out
docker run --rm -v "$PWD/out":/data plantuml/plantuml -tpng "/data/*.puml"
echo "PNGs written to out/"
