#include <string.h>
#include "memory_pool.h"

/*
 * Linear memory pool allocation. The first sizeof(size_t) bytes of pool_buffer
 * hold the number of bytes already used in the data area that follows.
 * Returns 0 on success, -1 on invalid parameters or insufficient space.
 * The pool (including its header) is left unchanged on failure.
 */
int allocate_pool_memory(const char* init_data, size_t data_len, char* pool_buffer, size_t pool_size) {
    const size_t header = sizeof(size_t);
    size_t available;
    size_t used;

    if (pool_buffer == NULL || pool_size < header) {
        return -1;
    }
    if (init_data == NULL) {
        /* Allocation without data is only valid for a zero-length request. */
        return (data_len == 0) ? 0 : -1;
    }

    available = pool_size - header;
    memcpy(&used, pool_buffer, header);

    /* Reject a corrupted header and any request that does not fit.
     * Written as a subtraction so used + data_len cannot wrap around. */
    if (used > available || data_len > available - used) {
        return -1;
    }

    if (data_len > 0) {
        memcpy(pool_buffer + header + used, init_data, data_len);
    }
    used += data_len;
    memcpy(pool_buffer, &used, header);
    return 0;
}
