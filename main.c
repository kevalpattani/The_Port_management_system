// what.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>     // For HTTP requests
#include <jansson.h>       // For JSON parsing
#include <unistd.h>        // For sleep, read (Linux/macOS)
#include <time.h>          // For time() and difftime()
#include <sys/time.h>      // For select, fd_set
#include <termios.h>       // For non-blocking terminal input (Linux/macOS)
#include <fcntl.h>         // For fcntl (Linux/macOS)

// --- Data Structures for C Client's Internal State ---
#define MAX_SHIPS 100 // Max number of ships to track internally
#define MESSAGE_BUFFER_SIZE 256 // Max size for emergency messages

typedef struct {
    int id;
    char name[50];
    char zone[50];
    char last_event_timestamp[30]; // ISO format timestamp of last event for this ship
    int is_active; // 1 if active, 0 if deleted/undocked and gone
} Ship;

Ship active_ships[MAX_SHIPS]; // Array to store current state of ships
int num_active_ships = 0;     // Counter for active ships

// --- Global Termios State for Non-Blocking Input ---
static struct termios old_tio, new_tio;

// Function to set stdin to non-canonical (raw) mode and non-blocking
void set_nonblocking_stdin() {
    tcgetattr(STDIN_FILENO, &old_tio); // Save current terminal settings
    new_tio = old_tio;
    new_tio.c_lflag &= (~ICANON & ~ECHO); // Disable canonical mode (line buffering) and echo
    new_tio.c_cc[VMIN] = 0;  // Minimum number of characters for non-blocking read
    new_tio.c_cc[VTIME] = 0; // Timeout in 0.1s for non-blocking read
    tcsetattr(STDIN_FILENO, TCSANOW, &new_tio); // Apply new settings immediately
    // Also set O_NONBLOCK flag for read()
    fcntl(STDIN_FILENO, F_SETFL, fcntl(STDIN_FILENO, F_GETFL) | O_NONBLOCK);
}

// Function to restore stdin to its original blocking mode
void restore_blocking_stdin() {
    tcsetattr(STDIN_FILENO, TCSANOW, &old_tio); // Restore old settings
    // Clear O_NONBLOCK flag
    fcntl(STDIN_FILENO, F_SETFL, fcntl(STDIN_FILENO, F_GETFL) & ~O_NONBLOCK);
}


// --- CURL Callback and Memory Struct (from previous versions) ---
struct MemoryStruct {
    char *memory;
    size_t size;
};

static size_t WriteMemoryCallback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    struct MemoryStruct *mem = (struct MemoryStruct *)userp;

    // Reallocate memory to accommodate new data + null terminator
    char *ptr = realloc(mem->memory, mem->size + realsize + 1);
    if(ptr == NULL) {
        fprintf(stderr, "Error: Not enough memory (realloc returned NULL)\n");
        return 0; // Indicate error
    }
    mem->memory = ptr;
    memcpy(&(mem->memory[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->memory[mem->size] = 0; // Null-terminate the string
    return realsize;
}

// --- Helper Functions for Ship Management ---

// Find a ship by ID. Returns pointer to Ship struct or NULL if not found.
Ship* find_ship(int ship_id) {
    for (int i = 0; i < num_active_ships; i++) {
        if (active_ships[i].id == ship_id) {
            return &active_ships[i];
        }
    }
    return NULL;
}

// Add or update a ship's details in the active_ships array
void update_ship_state(int id, const char* name, const char* zone, const char* timestamp, int is_active) {
    Ship* ship = find_ship(id);
    if (ship) {
        // Update existing ship
        strncpy(ship->name, name, sizeof(ship->name) - 1);
        ship->name[sizeof(ship->name) - 1] = '\0'; // Ensure null termination
        strncpy(ship->zone, zone, sizeof(ship->zone) - 1);
        ship->zone[sizeof(ship->zone) - 1] = '\0'; // Ensure null termination
        strncpy(ship->last_event_timestamp, timestamp, sizeof(ship->last_event_timestamp) - 1);
        ship->last_event_timestamp[sizeof(ship->last_event_timestamp) - 1] = '\0'; // Ensure null termination
        ship->is_active = is_active;
    } else {
        // Add new ship if space available
        if (num_active_ships < MAX_SHIPS) {
            active_ships[num_active_ships].id = id;
            strncpy(active_ships[num_active_ships].name, name, sizeof(active_ships[num_active_ships].name) - 1);
            active_ships[num_active_ships].name[sizeof(active_ships[num_active_ships].name) - 1] = '\0';
            strncpy(active_ships[num_active_ships].zone, zone, sizeof(active_ships[num_active_ships].zone) - 1);
            active_ships[num_active_ships].zone[sizeof(active_ships[num_active_ships].zone) - 1] = '\0';
            strncpy(active_ships[num_active_ships].last_event_timestamp, timestamp, sizeof(active_ships[num_active_ships].last_event_timestamp) - 1);
            active_ships[num_active_ships].last_event_timestamp[sizeof(active_ships[num_active_ships].last_event_timestamp) - 1] = '\0';
            active_ships[num_active_ships].is_active = is_active;
            num_active_ships++;
        } else {
            fprintf(stderr, "Warning: Max ships reached. Cannot add new ship ID %d.\n", id);
        }
    }
}

// Remove a ship from the active_ships array (e.g., if it's "deleted" or "undocked and went away")
void remove_ship(int ship_id) {
    for (int i = 0; i < num_active_ships; i++) {
        if (active_ships[i].id == ship_id) {
            // Shift elements to fill the gap
            for (int j = i; j < num_active_ships - 1; j++) {
                active_ships[j] = active_ships[j + 1];
            }
            num_active_ships--;
            printf("[INFO] Ship ID %d removed from active list.\n", ship_id);
            return;
        }
    }
}

// --- Function to Send Emergency Message to Pygame ---
void send_emergency_message(const char* message_content) {
    CURL *curl;
    CURLcode res;
    struct MemoryStruct chunk;
    chunk.memory = malloc(1);
    chunk.size = 0;

    curl_global_init(CURL_GLOBAL_DEFAULT); // This is safe to call multiple times, but good practice is once
    curl = curl_easy_init();
    if (curl) {
        // IMPORTANT: Update this URL if your FastAPI server is on a different IP/port
        curl_easy_setopt(curl, CURLOPT_URL, "http://127.0.0.1:8000/send_message_to_pygame");
        curl_easy_setopt(curl, CURLOPT_POST, 1L);

        char json_payload[MESSAGE_BUFFER_SIZE + 30]; // Enough for {"message":"..."}
        snprintf(json_payload, sizeof(json_payload), "{\"message\":\"%s\"}", message_content);

        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json_payload);
        struct curl_slist *headers = NULL;
        headers = curl_slist_append(headers, "Content-Type: application/json");
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteMemoryCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&chunk);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L); // Timeout for sending message

        printf("\nSending emergency message: '%s'...\n", message_content);
        res = curl_easy_perform(curl);

        if (res != CURLE_OK) {
            fprintf(stderr, "send_emergency_message failed: %s\n", curl_easy_strerror(res));
        } else {
            printf("Message sent successfully. Server response: %s\n", chunk.memory);
        }

        curl_easy_cleanup(curl);
        curl_slist_free_all(headers);
    } else {
        fprintf(stderr, "Error: Could not initialize curl handle for sending message.\n");
    }
    free(chunk.memory);
    // curl_global_cleanup(); // Do not call here, only once at program end
}


// --- Main Program Loop ---
int main(void) {
    CURL *curl_handle;
    long last_log_entry_count = 0; // To keep track of already processed logs
    const int poll_interval_ms = 1000; // Poll every 1000ms (1 second)

    // Set stdin to non-blocking mode
    set_nonblocking_stdin();

    // Register cleanup function to restore terminal settings on exit
    atexit(restore_blocking_stdin);

    // Initialize libcurl global environment (only once at program start)
    curl_global_init(CURL_GLOBAL_DEFAULT);

    printf("C Client for Port Simulation - Polling logs and sending messages.\n");
    printf("Press 'e' to type an emergency message.\n");
    printf("-----------------------------------------------------------------\n");

    char emergency_message_buffer[MESSAGE_BUFFER_SIZE];
    int in_emergency_input_mode = 0; // Flag to indicate if we are collecting emergency message
    int emergency_msg_idx = 0; // Current index in buffer for emergency message

    while (1) {
        // --- API Polling Logic ---
        struct MemoryStruct chunk;
        chunk.memory = malloc(1);
        chunk.size = 0;

        curl_handle = curl_easy_init();
        if (curl_handle) {
            // Set the URL for the GET request to fetch logs
            // IMPORTANT: Update this URL if your FastAPI server is on a different IP/port
            curl_easy_setopt(curl_handle, CURLOPT_URL, "http://127.0.0.1:8000/get_logs");
            curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION, WriteMemoryCallback);
            curl_easy_setopt(curl_handle, CURLOPT_WRITEDATA, (void *)&chunk);
            curl_easy_setopt(curl_handle, CURLOPT_TIMEOUT, 5L); // Timeout after 5 seconds

            CURLcode res = curl_easy_perform(curl_handle);

            long http_code = 0;
            curl_easy_getinfo(curl_handle, CURLINFO_RESPONSE_CODE, &http_code);

            if (res != CURLE_OK) {
                fprintf(stderr, "curl_easy_perform() failed: %s\n", curl_easy_strerror(res));
            } else if (http_code != 200) {
                 fprintf(stderr, "HTTP Request failed with status code %ld: %s\n", http_code, chunk.memory);
            } else {
                json_error_t error;
                json_t *root = json_loads(chunk.memory, 0, &error);

                if (!root) {
                    fprintf(stderr, "Error parsing JSON at line %d: %s (text: '%.*s')\n",
                            error.line, error.text, 50, chunk.memory);
                } else {
                    json_t *status_obj = json_object_get(root, "status");
                    json_t *logs_array = json_object_get(root, "logs");

                    if (json_is_string(status_obj) && strcmp(json_string_value(status_obj), "success") == 0 && json_is_array(logs_array)) {
                        long current_total_logs = json_array_size(logs_array);

                        if (current_total_logs > last_log_entry_count) {
                            // printf("\n--- Processing New Events (%ld total logs) ---\n", current_total_logs);
                            for (long i = last_log_entry_count; i < current_total_logs; i++) {
                                json_t *log_entry = json_array_get(logs_array, i);
                                if (json_is_object(log_entry)) {
                                    json_t *ship_id_obj = json_object_get(log_entry, "ship_id");
                                    json_t *ship_name_obj = json_object_get(log_entry, "ship_name");
                                    json_t *current_zone_obj = json_object_get(log_entry, "current_zone");
                                    json_t *timestamp_obj = json_object_get(log_entry, "timestamp");
                                    json_t *event_type_obj = json_object_get(log_entry, "event_type");
                                    json_t *message_obj = json_object_get(log_entry, "message");

                                    int ship_id = json_is_integer(ship_id_obj) ? (int)json_integer_value(ship_id_obj) : -1;
                                    const char* ship_name = json_is_string(ship_name_obj) ? json_string_value(ship_name_obj) : "N/A";
                                    const char* current_zone = json_is_string(current_zone_obj) ? json_string_value(current_zone_obj) : "N/A";
                                    const char* timestamp = json_is_string(timestamp_obj) ? json_string_value(timestamp_obj) : "N/A";
                                    const char* event_type = json_is_string(event_type_obj) ? json_string_value(event_type_obj) : "unknown";
                                    const char* message = json_is_string(message_obj) ? json_string_value(message_obj) : "";


                                    // Handle different event types
                                    if (strcmp(event_type, "emergency") == 0 || strcmp(event_type, "emergency_global") == 0) {
                                        printf("\n[!!! EMERGENCY !!!] ");
                                        if (ship_id != 0) { // If it's a ship-specific emergency
                                            printf("Ship %s (ID: %d) at zone %s, ", ship_name, ship_id, current_zone);
                                        } else { // Global emergency
                                            printf("GLOBAL Emergency: ");
                                        }
                                        printf("Time: %s - Message: %s\n", timestamp, message);
                                    } else if (strcmp(event_type, "ship_deleted") == 0) {
                                        printf("\n[DELETED] Ship %s (ID: %d) has left the simulation. Time: %s\n", ship_name, ship_id, timestamp);
                                        remove_ship(ship_id); // Remove from our internal active list
                                    } else if (strcmp(event_type, "undocked") == 0) {
                                        printf("\n[UNDOCKED] Ship %s (ID: %d) undocked from terminal %s. Time: %s\n", ship_name, ship_id, json_is_integer(json_object_get(log_entry, "parked_terminal")) ? "" : "(N/A)", timestamp);
                                        // For undocked, it's still active, but its zone might change
                                        update_ship_state(ship_id, ship_name, "Undocked (Moving Away)", timestamp, 1);
                                    }
                                    else {
                                        // Regular ship update event (zone_change, docked, etc.)
                                        printf("\n[UPDATE] Ship: %s (ID: %d), Zone: %s, Time: %s\n",
                                               ship_name, ship_id, current_zone, timestamp);
                                        update_ship_state(ship_id, ship_name, current_zone, timestamp, 1); // Mark as active
                                    }
                                }
                            }
                            last_log_entry_count = current_total_logs; // Update the count
                            // Re-print current active ships after updates
                            printf("\n--- Current Active Ships (%d total) ---\n", num_active_ships);
                            for (int i = 0; i < num_active_ships; i++) {
                                if (active_ships[i].is_active) {
                                    printf("  ID: %d, Name: %s, Zone: %s\n", active_ships[i].id, active_ships[i].name, active_ships[i].zone);
                                }
                            }
                            printf("---------------------------------------\n");

                        }
                    } else {
                        fprintf(stderr, "JSON structure invalid (missing 'status' or 'logs' array).\n");
                    }
                    json_decref(root); // Free the JSON object
                }
            }
            curl_easy_cleanup(curl_handle);
            free(chunk.memory); // Free the allocated memory for the response chunk
        } else {
            fprintf(stderr, "Error: Could not initialize curl handle.\n");
        }

        // --- Non-Blocking Input Logic ---
        fd_set fds;
        struct timeval tv;
        int retval;
        char c;

        FD_ZERO(&fds);
        FD_SET(STDIN_FILENO, &fds);

        tv.tv_sec = 0;
        tv.tv_usec = 10000; // Check for input every 10ms (to not block polling too much)

        retval = select(STDIN_FILENO + 1, &fds, NULL, NULL, &tv);

        if (retval == -1) {
            perror("select()");
        } else if (retval) {
            // Input is available
            if (read(STDIN_FILENO, &c, 1) > 0) {
                if (in_emergency_input_mode) {
                    if (c == '\n' || c == '\r') { // Enter key pressed
                        emergency_message_buffer[emergency_msg_idx] = '\0'; // Null-terminate
                        if (strlen(emergency_message_buffer) > 0) {
                            send_emergency_message(emergency_message_buffer);
                        } else {
                            printf("Emergency message cancelled or empty.\n");
                        }
                        in_emergency_input_mode = 0;
                        emergency_msg_idx = 0;
                        printf("-----------------------------------------------------------------\n"); // Clean up prompt
                        printf("C Client for Port Simulation - Polling logs and sending messages.\n");
                        printf("Press 'e' to type an emergency message.\n");
                        printf("-----------------------------------------------------------------\n");
                    } else if (c == 127 || c == '\b') { // Backspace (ASCII 127 or 8)
                        if (emergency_msg_idx > 0) {
                            emergency_msg_idx--;
                            emergency_message_buffer[emergency_msg_idx] = '\0';
                            printf("\b \b"); // Erase character from console
                            fflush(stdout);
                        }
                    } else if (emergency_msg_idx < MESSAGE_BUFFER_SIZE - 1) {
                        emergency_message_buffer[emergency_msg_idx++] = c;
                        emergency_message_buffer[emergency_msg_idx] = '\0'; // Keep null-terminated
                        printf("%c", c); // Echo character
                        fflush(stdout);
                    }
                } else {
                    if (c == 'e' || c == 'E') {
                        in_emergency_input_mode = 1;
                        emergency_msg_idx = 0;
                        emergency_message_buffer[0] = '\0';
                        printf("\n--- EMERGENCY MESSAGE INPUT --- (Press Enter to send, Backspace to delete)\n");
                        printf("Message: ");
                        fflush(stdout);
                    } else {
                        // printf("Key pressed: %c\n", c); // For debugging other keys
                    }
                }
            }
        }
        
        // Short sleep to prevent busy-waiting if select returns immediately
        usleep(100000); // 100ms sleep (0.1 seconds)
    }

    // This part will not be reached in an infinite loop
    restore_blocking_stdin(); // Ensure terminal is restored on manual exit (Ctrl+C)
    curl_global_cleanup();
    return 0;
}
