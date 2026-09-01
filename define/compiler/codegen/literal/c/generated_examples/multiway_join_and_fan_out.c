#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned char test_particle;
static unsigned char box_particle;
static unsigned char box_position_a_particle;
static unsigned char box_position_b_particle;

[[noreturn]] static void fail_thread_operation(
    const char *operation, int error_number
) {
    errno = error_number;
    perror(operation);
    _Exit(EXIT_FAILURE);
}

static void *create_and_destroy_box_position_a(void *unused) {
    (void)unused;
    box_position_a_particle = 1;
    box_position_a_particle = 0;
    return NULL;
}

static void create_and_destroy_box_position_b(void) {
    box_position_b_particle = 1;
    box_position_b_particle = 0;
}

static void action_test(void) {
    box_particle = 1;

    pthread_t box_position_a_thread;
    int error_number = pthread_create(
        &box_position_a_thread,
        NULL,
        create_and_destroy_box_position_a,
        NULL
    );
    if (error_number != 0) {
        fail_thread_operation("pthread_create", error_number);
    }

    create_and_destroy_box_position_b();

    error_number = pthread_join(box_position_a_thread, NULL);
    if (error_number != 0) {
        fail_thread_operation("pthread_join", error_number);
    }
    box_particle = 0;
}

int main(void) {
    test_particle = 1;
    action_test();
    return 0;
}
