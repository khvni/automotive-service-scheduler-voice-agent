#!/bin/bash
set -e

echo "=================================================="
echo "Running Code Quality Checks"
echo "=================================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to project root
cd "$(dirname "$0")/.."

echo ""
echo -e "${BLUE}1. Running Black formatter check...${NC}"
black --check server/app server/tests worker scripts || {
    echo -e "${RED}Black formatting issues found. Run './scripts/format_code.sh' to fix.${NC}"
    exit 1
}
echo -e "${GREEN}✓ Black formatting OK${NC}"

echo ""
echo -e "${BLUE}2. Running isort check...${NC}"
isort --check server/app server/tests worker scripts || {
    echo -e "${RED}Import sorting issues found. Run './scripts/format_code.sh' to fix.${NC}"
    exit 1
}
echo -e "${GREEN}✓ Import sorting OK${NC}"

echo ""
echo -e "${BLUE}3. Running flake8 linter...${NC}"
flake8 server/app worker || {
    echo -e "${RED}Flake8 linting issues found.${NC}"
    exit 1
}
echo -e "${GREEN}✓ Flake8 OK${NC}"

echo ""
echo -e "${BLUE}4. Running mypy type checker...${NC}"
mypy server/app worker || {
    echo -e "${RED}MyPy type checking issues found.${NC}"
    exit 1
}
echo -e "${GREEN}✓ MyPy OK${NC}"

echo ""
echo -e "${BLUE}5. Running pylint...${NC}"
pylint server/app worker --rcfile=.pylintrc || {
    echo -e "${RED}Pylint issues found.${NC}"
    exit 1
}
echo -e "${GREEN}✓ Pylint OK${NC}"

echo ""
echo -e "${BLUE}6. Running bandit security checks...${NC}"
bandit -r server/app worker -ll || {
    echo -e "${RED}Security issues found.${NC}"
    exit 1
}
echo -e "${GREEN}✓ Security checks OK${NC}"

echo ""
echo "=================================================="
echo -e "${GREEN}All code quality checks passed!${NC}"
echo "=================================================="
