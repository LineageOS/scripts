TARGETS := carrierId_pb2.py carrier_list_pb2.py  carrier_settings_pb2.py

.PHONY: all clean
all: $(TARGETS)
clean:
	rm -f $(TARGETS)

%_pb2.py: %.proto
	protoc --python_out=. $<
