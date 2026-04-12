# Define variables with defaults
REGISTRY ?=
IMAGE_OWNER ?=
IMAGE_NAME ?= tc31-xar-base
IMAGE_TAG ?= latest

IMAGE = $(REGISTRY)$(IMAGE_OWNER)$(IMAGE_NAME):$(IMAGE_TAG)

APT_AUTH_CONF ?= ./tc31-xar-base/apt-config/bhf.conf
DOCKERFILE ?= ./tc31-xar-base/Dockerfile
BUILD_CONTEXT ?= ./tc31-xar-base

CONTAINER_ENGINE ?= docker
COMPOSE = $(CONTAINER_ENGINE) compose
COMPOSE_TEST = $(COMPOSE) -f docker-compose.yaml -f docker-compose.test.yaml
PYTEST ?= pytest

.DEFAULT_GOAL := help

build-image:
	@if [ ! -f "$(APT_AUTH_CONF)" ]; then \
		echo "ERROR: $(APT_AUTH_CONF) missing. Copy $(APT_AUTH_CONF).example and fill in your myBeckhoff credentials." >&2; \
		exit 1; \
	fi
	@echo "Building image: $(IMAGE) (engine: $(CONTAINER_ENGINE))"
	$(CONTAINER_ENGINE) build --no-cache --secret id=apt,src=$(APT_AUTH_CONF) --network host -t $(IMAGE) -f $(DOCKERFILE) $(BUILD_CONTEXT)

push-image:
	@echo "Pushing image: $(IMAGE)"
	$(CONTAINER_ENGINE) push $(IMAGE)

run-containers:
	@echo "Starting containers..."
	$(COMPOSE) up -d

# List all containers managed by compose
list-containers:
	@echo "Listing containers..."
	$(COMPOSE) ps -a

# Stop and remove containers managed by compose
stop-and-remove-containers:
	@echo "Stopping and removing containers..."
	$(COMPOSE) down

# Show logs for containers managed by compose
container-logs:
	@echo "Showing container logs..."
	$(COMPOSE) logs -ft

# Run unit tests (no containers needed)
test-unit:
	$(PYTEST) tests/unit -v

# Run e2e tests (brings up test stack via compose overlay)
test-e2e:
	$(PYTEST) tests/e2e -v

test-all: test-unit test-e2e

# Start the test stack (compose + overlay, port-mapped for host access)
test-stack-up:
	$(COMPOSE_TEST) up -d

test-stack-down:
	$(COMPOSE_TEST) down -v

# Display help information
help:
	@echo "Available targets:"
	@echo "  build-image                Build the container image ($(CONTAINER_ENGINE))"
	@echo "  push-image                 Push the container image to the registry"
	@echo "  run-containers             Start containers (base compose)"
	@echo "  list-containers            List all containers managed by compose"
	@echo "  stop-and-remove-containers Stop and remove containers managed by compose"
	@echo "  container-logs             Show logs for containers managed by compose"
	@echo "  test-unit                  Run unit tests (pytest tests/unit)"
	@echo "  test-e2e                   Run end-to-end tests (pytest tests/e2e)"
	@echo "  test-all                   Run unit + e2e tests"
	@echo "  test-stack-up              Bring up the test stack (compose overlay)"
	@echo "  test-stack-down            Tear down the test stack"
	@echo "  help                       Display this help message"
	@echo ""
	@echo "Variables: CONTAINER_ENGINE=$(CONTAINER_ENGINE)  IMAGE=$(IMAGE)"
