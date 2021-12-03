TARGETS := carriersettings_pb2.py carrierId_pb2.py

.PHONY: all clean
all: $(TARGETS)
clean:
	rm -f $(TARGETS)

%_pb2.py: %.proto
	protoc --python_out=. $<
