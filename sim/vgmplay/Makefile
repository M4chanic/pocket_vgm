JT51_HDL := ../../rtl/vendor/jt51/hdl
JT51_SRC := $(addprefix $(JT51_HDL)/,$(shell grep -v '\.\./' $(JT51_HDL)/jt51.f))

vgmplay: main.cpp $(JT51_SRC)
	verilator --cc --exe --build -O3 -Wno-fatal --top-module jt51 \
		$(JT51_SRC) main.cpp -CFLAGS "-O2" -LDFLAGS "-lz" -o ../$@

clean:
	rm -rf obj_dir vgmplay

.PHONY: clean
