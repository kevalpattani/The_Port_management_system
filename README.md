# The_Port_management_system
ok ok 

# Please change the ip addrs from YOUR_LOCAL_IP to your local ip addr 

for the ship_data.py Download following libraries
  1. pygame
  2. requests

for the server.py Download following libraries
  1. fastapi
  2. uvicorn

for the main.c make sure about launch.json and tasks.json in the vs code and change it accordingly to run not-inbuilt libraries.

<details>

<summary> tasks.json </summary>

```
// .vscode/tasks.json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "build what.c", // A descriptive name for this build task
            "type": "shell",         // Specifies that this is a shell command
            "command": "gcc",        // The compiler command (GNU C Compiler)
            "args": [
                "${workspaceFolder}/what.c", // Path to your C source file
                "-o",                       // Output file flag
                "${workspaceFolder}/what", // Name of the executable output file (e.g., 'what')
                "-lcurl",                   // Link with the libcurl library
                "-ljansson",                // Link with the jansson JSON parsing library
                // On Windows with MSYS2/MinGW, you might need to specify include and library paths:
                // "-I/path/to/msys64/mingw64/include", // Example include path
                // "-L/path/to/msys64/mingw64/lib"      // Example library path
            ],
            "group": {
                "kind": "build",
                "isDefault": true // Makes this the default build task (Ctrl+Shift+B)
            },
            "problemMatcher": [
                "$gcc" // Uses VS Code's built-in GCC problem matcher for error/warning detection
            ],
            "detail": "Compiles what.c and links with libcurl and jansson."
        }
    ]
}
```
</details>


----

<details>

<summary> launch.json </summary>

```
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Launch what.c", // A descriptive name for this launch configuration
            "type": "cppdbg",       // Specifies the debugger type for C/C++
            "request": "launch",    // Indicates that this configuration is for launching a program
            "program": "<span class="math-inline">\{workspaceFolder\}/what", // Path to the executable compiled by tasks\.json
"args"\: \[\],             // Command\-line arguments to pass to your program
"stopAtEntry"\: false,   // If true, the debugger will stop at the beginning of main\(\)
"cwd"\: "</span>{workspaceFolder}", // The current working directory when the program runs
            "environment": [],      // Environment variables to set for the program
            "externalConsole": true, // If true, the program's output will appear in a new terminal window
            "MIMode": "gdb",        // The debugger backend (gdb for GCC, lldb for Clang/macOS)
            "setupCommands": [
                {
                    "description": "Enable pretty-printing for gdb",
                    "text": "-enable-pretty-printing",
                    "ignoreFailures": true
                }
            ],
            "preLaunchTask": "build what.c" // This task will be executed before launching the program
        }
    ]
}

```
</details>

also we are using #include curl/curl.h, jansson.h in main.c
