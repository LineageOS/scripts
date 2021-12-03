TARGETS := carriersettings_pb2.py vendor/carrierId_pb2.py vendor/carrierId.proto

.PHONY: all clean
all: $(TARGETS)
clean:
	rm -f $(TARGETS)

%_pb2.py: %.proto
	protoc --python_out=. $<

vendor/carrierId.proto:
	wget -qO- \
	https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/heads/master/proto/src/carrierId.proto?format=TEXT | \
	base64 --decode > $@
