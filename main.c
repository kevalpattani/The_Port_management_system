#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h> // For HTTP requests
#include <jansson.h>   // For JSON parsing
#include <unistd.h>    // For sleep (on Linux/macOS)
// #include <windows.h> // For Sleep (on Windows, comment out unistd.h if exclusively Windows)

// Structure to hold the data received from the server
struct MemoryStruct {
    char *memory;
    size_t size;
};

// Callback function to write received data into our MemoryStruct
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

int main(void) {
    CURL *curl_handle;
    CURLcode res;
    long last_log_count = 0; // To keep track of already processed logs

    // Initialize libcurl global environment
    curl_global_init(CURL_GLOBAL_DEFAULT);

    while (1) { // Infinite loop for continuous fetching
        struct MemoryStruct chunk;
        chunk.memory = malloc(1); // Will be grown as needed by realloc
        chunk.size = 0;           // No data at this point

        // Initialize a new curl handle for each request to avoid stale states
        // This is important for robustness in a continuous loop
        curl_handle = curl_easy_init();
        if (curl_handle) {
            // Set the URL for the GET request
            // IMPORTANT: Replace with the actual IP address of your FastAPI server
            // Example: "http://172.16.3.228:8000/get_logs"
            curl_easy_setopt(curl_handle, CURLOPT_URL, "http://YOUR_LOCAL_IP/get_logs");

            // Set callback to capture the server's response
            curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION, WriteMemoryCallback);
            curl_easy_setopt(curl_handle, CURLOPT_WRITEDATA, (void *)&chunk);

            // Perform the request
            res = curl_easy_perform(curl_handle);

            // Check for HTTP response code
            long http_code = 0;
            curl_easy_getinfo(curl_handle, CURLINFO_RESPONSE_CODE, &http_code);


            if (res != CURLE_OK) {
                fprintf(stderr, "curl_easy_perform() failed: %s\n", curl_easy_strerror(res));
            } else if (http_code != 200) {
                 fprintf(stderr, "HTTP Request failed with status code %ld: %s\n", http_code, chunk.memory);
            }
            else {
                // Successfully fetched data, now parse it
                json_error_t error;
                json_t *root = json_loads(chunk.memory, 0, &error);

                if (!root) {
                    fprintf(stderr, "Error parsing JSON at line %d: %s (text: '%.*s')\n",
                            error.line, error.text, 50, chunk.memory);
                } else {
                    json_t *status_obj = json_object_get(root, "status");
                    json_t *logs_array = json_object_get(root, "logs");

                    if (json_is_string(status_obj) && strcmp(json_string_value(status_obj), "success") == 0 && json_is_array(logs_array)) {
                        long current_log_count = json_array_size(logs_array);

                        // Only process new logs
                        if (current_log_count > last_log_count) {
                            printf("\n--- New Log Entries (%ld total, %ld new) ---\n", current_log_count, current_log_count - last_log_count);
                            for (long i = last_log_count; i < current_log_count; i++) {
                                json_t *log_entry = json_array_get(logs_array, i);
                                if (json_is_object(log_entry)) {
                                    json_t *ship_name_obj = json_object_get(log_entry, "ship_name");
                                    json_t *current_zone_obj = json_object_get(log_entry, "current_zone");

                                    if (json_is_string(ship_name_obj) && json_is_string(current_zone_obj)) {
                                        printf("Ship Name: %s, Zone: %s\n",
                                               json_string_value(ship_name_obj),
                                               json_string_value(current_zone_obj));
                                    }
                                }
                            }
                            printf("---------------------------------------\n");
                            last_log_count = current_log_count; // Update the count of processed logs
                        } else {
                            // printf("No new log entries.\n"); // Optional: for debugging, but can be noisy
                        }
                    } else {
                        fprintf(stderr, "JSON structure invalid (missing 'status' or 'logs' array).\n");
                    }
                    json_decref(root); // Free the JSON object
                }
            }

            // Clean up curl handle for this iteration
            curl_easy_cleanup(curl_handle);
        } else {
            fprintf(stderr, "Error: Could not initialize curl handle.\n");
        }

        // Free the allocated memory for the response chunk
        free(chunk.memory);

        // Wait for 1 second before the next request
        sleep(1); // On Windows, use Sleep(1000); (Note: Sleep is in milliseconds)
    }

    // curl_global_cleanup() will not be reached in this infinite loop unless exited manually

    return 0;
}
