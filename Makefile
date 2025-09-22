.PHONY: datetime-date datetime-full datetime-filename datetime help

# Date-time outputs for different use cases
datetime-date:
	@date '+%Y-%m-%d'

datetime-full:
	@date '+%Y-%m-%d %H:%M:%S'

datetime-filename:
	@date '+%Y-%m-%d-%H-%M-%S'

# Convenience target (defaults to full format)
datetime: datetime-full

# --- Help -------------------------------------------------------------------
help:
	@echo "Available targets:"
	@echo ""
	@echo "Date-time targets:"
	@echo "  datetime-date     - output current date in YYYY-MM-DD format"
	@echo "  datetime-full     - output current date-time in YYYY-MM-DD HH:MM:SS format"
	@echo "  datetime-filename - output current date-time in YYYY-MM-DD-HH-MM-SS format"
	@echo "  datetime          - convenience target (defaults to datetime-full)"