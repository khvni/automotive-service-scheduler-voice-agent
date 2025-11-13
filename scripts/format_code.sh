#!/bin/bash
set -e

echo "=================================================="
echo "Formatting Code"
echo "=================================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to project root
cd "$(dirname "$0")/.."

echo ""
echo -e "${BLUE}1. Running Black formatter...${NC}"
black server/app server/tests worker scripts
echo -e "${GREEN}✓ Black formatting complete${NC}"

echo ""
echo -e "${BLUE}2. Running isort...${NC}"
isort server/app server/tests worker scripts
echo -e "${GREEN}✓ Import sorting complete${NC}"

echo ""
echo "=================================================="
echo -e "${GREEN}Code formatting complete!${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Review the changes with 'git diff'"
echo "  2. Run './scripts/check_code_quality.sh' to verify"
echo "  3. Commit the changes"
