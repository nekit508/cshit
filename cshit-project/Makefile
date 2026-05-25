COMPILER = D:\projects\python\compiler\.venv\Scripts\python.exe ../main.py
LINKER = ld --subsystem console

LIBRARIES = -L"D:/soft/mingw64/x86_64-w64-mingw32/lib" -lmsvcrt -lkernel32 -e main

BUILD_DIR = ./build/
INCLUDE_DIR = ./include/
SRC_DIR = ./src/

OBJ_DIR = $(BUILD_DIR)obj/

OUTPUT_EXECUTABLE = main.exe

# -tD

SRCS = $(wildcard $(SRC_DIR)*.cs)
OBJS = $(patsubst $(SRC_DIR)%.cs,$(OBJ_DIR)%.o,$(SRCS))

$(BUILD_DIR) $(OBJ_DIR):
	mkdir -p $@

$(OBJ_DIR)%.o: $(SRC_DIR)%.cs | $(OBJ_DIR)
	$(COMPILER) $< -o $@

objects: $(OBJS)


link: $(OBJS)
	$(LINKER) $< $(LIBRARIES) -o $(BUILD_DIR)$(OUTPUT_EXECUTABLE)

$(BUILD_DIR)$(OUTPUT_EXECUTABLE): link

run: $(BUILD_DIR)$(OUTPUT_EXECUTABLE)
	$(BUILD_DIR)$(OUTPUT_EXECUTABLE)

clean:
	rm -f $(OBJS)