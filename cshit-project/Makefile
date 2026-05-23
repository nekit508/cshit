COMPILER = D:\projects\python\compiler\.venv\Scripts\python.exe ../main.py
LINKER = lld

BUILD_DIR = ./build/
INCLUDE_DIR = ./include/
SRC_DIR = ./src/

OBJ_DIR = $(BUILD_DIR)obj/

# -tD

SRCS = $(wildcard $(SRC_DIR)*.cs)
OBJS = $(patsubst $(SRC_DIR)%.cs,$(OBJ_DIR)%.o,$(SRCS))

$(BUILD_DIR) $(OBJ_DIR):
	mkdir -p $@

$(OBJ_DIR)%.o: $(SRC_DIR)%.cs | $(OBJ_DIR)
	$(COMPILER) $< -o $@

objects: $(OBJS)

link: $(OBJS)
	$(LINKER) $< -o $(BUILD_DIR)output.exe

clean:
	rm -f $(OBJS)