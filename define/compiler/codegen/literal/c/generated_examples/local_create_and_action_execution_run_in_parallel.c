#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned char test_particle;
static unsigned char other_trigger_particle;
static unsigned char other_item_particle;
static unsigned char local_item_particle;

[[noreturn]] static void fail_thread_operation(
    const char *operation, int error_number
) {
    errno = error_number;
    perror(operation);
    _Exit(EXIT_FAILURE);
}

static void action_other(void) {
    other_item_particle = 1;
    other_item_particle = 0;
}

static void *create_and_destroy_local_item(void *unused) {
    (void)unused;
    local_item_particle = 1;
    local_item_particle = 0;
    return NULL;
}

static void create_trigger_and_run_other_action(void) {
    other_trigger_particle = 1;
    action_other();
    other_trigger_particle = 0;
}

static void action_test(void) {
    pthread_t local_item_thread;
    int error_number = pthread_create(
        &local_item_thread, NULL, create_and_destroy_local_item, NULL
    );
    if (error_number != 0) {
        fail_thread_operation("pthread_create", error_number);
    }

    create_trigger_and_run_other_action();

    error_number = pthread_join(local_item_thread, NULL);
    if (error_number != 0) {
        fail_thread_operation("pthread_join", error_number);
    }
}

int main(void) {
    test_particle = 1;
    action_test();
    return 0;
}
