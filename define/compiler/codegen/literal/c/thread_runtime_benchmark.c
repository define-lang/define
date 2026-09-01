#define _GNU_SOURCE

#if !defined(__linux__) || !defined(__x86_64__)
#error "thread_runtime_benchmark.c currently requires Linux on x86-64"
#endif

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <linux/futex.h>
#include <linux/sched.h>
#include <sched.h>
#include <signal.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define DEFINE_THREAD_RUNTIME_FRESH_PTHREAD 1
#define DEFINE_THREAD_RUNTIME_PTHREAD_SPIN 2
#define DEFINE_THREAD_RUNTIME_PTHREAD_FUTEX 3
#define DEFINE_THREAD_RUNTIME_CLONE_SPIN 4
#define DEFINE_THREAD_RUNTIME_CLONE_FUTEX 5
#define DEFINE_THREAD_RUNTIME_DIRECT_SERIAL 6

#define COUNTER_VALUE_MASK (UINT_MAX >> 1)
#define COUNTER_WAITER_BIT (UINT_MAX - COUNTER_VALUE_MASK)

#define DEFINE_COMPLETION_COUNTER 1
#define DEFINE_COMPLETION_FLAGS 2
#define DEFINE_PUBLICATION_BROADCAST 1
#define DEFINE_PUBLICATION_TARGETED 2
#define DEFINE_RAW_STACK_MAPPED_GUARDED 1
#define DEFINE_RAW_STACK_MAPPED 2
#define DEFINE_RAW_STACK_STATIC 3
#define DEFINE_FUTEX_WAKE_WAITER_BIT 1
#define DEFINE_FUTEX_WAKE_UNCONDITIONAL 2

#define STRINGIFY_EXPANSION(value) #value
#define STRINGIFY(value) STRINGIFY_EXPANSION(value)

#if !defined(DEFINE_COMPLETION)
#if DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_PTHREAD_FUTEX \
    || DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_CLONE_FUTEX
#define DEFINE_COMPLETION DEFINE_COMPLETION_COUNTER
#else
#define DEFINE_COMPLETION DEFINE_COMPLETION_FLAGS
#endif
#endif

#if DEFINE_COMPLETION < DEFINE_COMPLETION_COUNTER \
    || DEFINE_COMPLETION > DEFINE_COMPLETION_FLAGS
#error "invalid completion representation"
#endif

#if !defined(DEFINE_PUBLICATION)
#define DEFINE_PUBLICATION DEFINE_PUBLICATION_BROADCAST
#endif

#if DEFINE_PUBLICATION < DEFINE_PUBLICATION_BROADCAST \
    || DEFINE_PUBLICATION > DEFINE_PUBLICATION_TARGETED
#error "invalid publication representation"
#endif

#if !defined(DEFINE_RAW_STACK)
#define DEFINE_RAW_STACK DEFINE_RAW_STACK_MAPPED_GUARDED
#endif

#if DEFINE_RAW_STACK < DEFINE_RAW_STACK_MAPPED_GUARDED \
    || DEFINE_RAW_STACK > DEFINE_RAW_STACK_STATIC
#error "invalid raw stack representation"
#endif

#if !defined(DEFINE_GENERATION_WAKE)
#define DEFINE_GENERATION_WAKE DEFINE_FUTEX_WAKE_WAITER_BIT
#endif

#if DEFINE_GENERATION_WAKE < DEFINE_FUTEX_WAKE_WAITER_BIT \
    || DEFINE_GENERATION_WAKE > DEFINE_FUTEX_WAKE_UNCONDITIONAL
#error "invalid generation wake protocol"
#endif

#if !defined(DEFINE_COMPLETION_WAKE)
#define DEFINE_COMPLETION_WAKE DEFINE_FUTEX_WAKE_WAITER_BIT
#endif

#if DEFINE_COMPLETION_WAKE < DEFINE_FUTEX_WAKE_WAITER_BIT \
    || DEFINE_COMPLETION_WAKE > DEFINE_FUTEX_WAKE_UNCONDITIONAL
#error "invalid completion wake protocol"
#endif

#if !defined(DEFINE_THREAD_RUNTIME)
#error "define DEFINE_THREAD_RUNTIME to one of the DEFINE_THREAD_RUNTIME_* values"
#endif

#if DEFINE_THREAD_RUNTIME < DEFINE_THREAD_RUNTIME_FRESH_PTHREAD \
    || DEFINE_THREAD_RUNTIME > DEFINE_THREAD_RUNTIME_DIRECT_SERIAL
#error "invalid thread runtime"
#endif

#if DEFINE_THREAD_RUNTIME >= DEFINE_THREAD_RUNTIME_FRESH_PTHREAD \
    && DEFINE_THREAD_RUNTIME <= DEFINE_THREAD_RUNTIME_PTHREAD_FUTEX
#define DEFINE_USES_PTHREAD 1
#include <pthread.h>
#else
#define DEFINE_USES_PTHREAD 0
#endif

#if DEFINE_THREAD_RUNTIME >= DEFINE_THREAD_RUNTIME_PTHREAD_SPIN \
    && DEFINE_THREAD_RUNTIME <= DEFINE_THREAD_RUNTIME_CLONE_FUTEX
#define DEFINE_USES_PERSISTENT_WORKERS 1
#else
#define DEFINE_USES_PERSISTENT_WORKERS 0
#endif

#if DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_PTHREAD_FUTEX \
    || DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_CLONE_FUTEX
#define DEFINE_USES_FUTEX_PARKING 1
#else
#define DEFINE_USES_FUTEX_PARKING 0
#endif

#if DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_CLONE_SPIN \
    || DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_CLONE_FUTEX
#define DEFINE_USES_RAW_CLONE 1
#else
#define DEFINE_USES_RAW_CLONE 0
#endif

#if DEFINE_USES_PERSISTENT_WORKERS \
    && DEFINE_COMPLETION == DEFINE_COMPLETION_FLAGS
#define DEFINE_USES_COMPLETION_FLAGS 1
#else
#define DEFINE_USES_COMPLETION_FLAGS 0
#endif

#if DEFINE_USES_PERSISTENT_WORKERS \
    && DEFINE_PUBLICATION == DEFINE_PUBLICATION_TARGETED
#define DEFINE_USES_TARGETED_PUBLICATION 1
#else
#define DEFINE_USES_TARGETED_PUBLICATION 0
#endif

enum {
    cache_line_size = 64,
    maximum_workers = 32,
    worker_stack_size = 1024 * 1024,
};

#if DEFINE_USES_RAW_CLONE && DEFINE_RAW_STACK == DEFINE_RAW_STACK_STATIC
alignas(4096) static unsigned char
    raw_worker_stacks[worker_stack_size * (maximum_workers - 1)];
#endif

static_assert(
    ATOMIC_INT_LOCK_FREE == 2,
    "the experiment requires always-lock-free unsigned-int atomics"
);

typedef struct Runtime Runtime;

typedef struct {
    size_t worker_count;
    size_t active_worker_count;
    size_t execution_count;
    unsigned int fast_work_amount;
    unsigned int slow_work_amount;
    size_t slow_worker_count;
    unsigned int idle_microseconds;
    unsigned int worker_spin_count;
    unsigned int caller_spin_count;
    size_t warmup_count;
    size_t sample_count;
    int processor_ids[maximum_workers];
} BenchmarkParameters;

typedef struct {
    alignas(cache_line_size) Runtime *runtime;
    size_t index;
    uint64_t state;
    size_t completed_execution_count;
#if DEFINE_USES_COMPLETION_FLAGS
    atomic_uint completed_generation;
#endif
#if DEFINE_USES_TARGETED_PUBLICATION
    atomic_uint requested_generation;
#endif
#if DEFINE_USES_PTHREAD && DEFINE_USES_PERSISTENT_WORKERS
    pthread_t thread;
#elif DEFINE_USES_RAW_CLONE
    atomic_int child_tid;
    int kernel_tid;
#endif
} RuntimeWorker;

struct Runtime {
    BenchmarkParameters parameters;
    alignas(cache_line_size) atomic_uint generation;
    alignas(cache_line_size) atomic_uint completed_workers;
    alignas(cache_line_size) atomic_uint ready_workers;
    atomic_bool stopping;
    RuntimeWorker workers[maximum_workers];
#if DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_FRESH_PTHREAD
    pthread_attr_t attributes[maximum_workers];
#elif DEFINE_USES_RAW_CLONE
    void *stack_arena;
    size_t stack_arena_size;
#endif
};

typedef struct {
    uint64_t startup_nanoseconds;
    uint64_t execution_nanoseconds;
    uint64_t processor_nanoseconds;
    uint64_t shutdown_nanoseconds;
    uint64_t checksum;
} BenchmarkSample;

[[noreturn]] static void fail_errno(const char *operation, int error_number) {
    errno = error_number;
    perror(operation);
    exit(EXIT_FAILURE);
}

[[noreturn]] static void fail_message(const char *message) {
    fputs(message, stderr);
    fputc('\n', stderr);
    exit(EXIT_FAILURE);
}

static uint64_t read_nanoseconds(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &now) != 0) {
        fail_errno("clock_gettime", errno);
    }
    return (uint64_t)now.tv_sec * UINT64_C(1000000000) + (uint64_t)now.tv_nsec;
}

static uint64_t read_processor_nanoseconds(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &now) != 0) {
        fail_errno("clock_gettime", errno);
    }
    return (uint64_t)now.tv_sec * UINT64_C(1000000000) + (uint64_t)now.tv_nsec;
}

static uint64_t idle_before_execution(unsigned int idle_microseconds) {
    if (idle_microseconds == 0) {
        return 0;
    }
    struct timespec requested = {
        .tv_sec = (time_t)(idle_microseconds / UINT64_C(1000000)),
        .tv_nsec = (long)(idle_microseconds % UINT64_C(1000000)) * 1000,
    };
    uint64_t start = read_nanoseconds();
    while (nanosleep(&requested, &requested) != 0) {
        if (errno != EINTR) {
            fail_errno("nanosleep", errno);
        }
    }
    return read_nanoseconds() - start;
}

static size_t parse_size(const char *text, const char *name) {
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value > SIZE_MAX) {
        fprintf(stderr, "invalid %s: %s\n", name, text);
        exit(EXIT_FAILURE);
    }
    return (size_t)value;
}

static unsigned int parse_unsigned(const char *text, const char *name) {
    size_t value = parse_size(text, name);
    if (value > UINT_MAX) {
        fprintf(stderr, "%s is too large: %s\n", name, text);
        exit(EXIT_FAILURE);
    }
    return (unsigned int)value;
}

#if DEFINE_USES_FUTEX_PARKING || DEFINE_USES_RAW_CLONE
static inline long raw_futex_call(
    const void *address, int operation, unsigned int value
) {
    long result;
    __asm__ volatile(
        "xor %%r10d,%%r10d\n\t"
        "xor %%r8d,%%r8d\n\t"
        "xor %%r9d,%%r9d\n\t"
        "syscall"
        : "=a"(result)
        : "0"(SYS_futex),
          "D"(address),
          "S"((long)operation),
          "d"((unsigned long)value)
        : "r10", "r8", "r9", "rcx", "r11", "memory"
    );
    return result;
}
#endif

#if DEFINE_USES_PERSISTENT_WORKERS
static void processor_relax(void) {
    __asm__ volatile("pause" ::: "memory");
}
#endif

#if DEFINE_USES_FUTEX_PARKING
static void futex_wait_private(
    const atomic_uint *value, unsigned int expected
) {
    (void)raw_futex_call(value, FUTEX_WAIT_PRIVATE, expected);
}

static void futex_wake_private(
    const atomic_uint *value, int maximum_waiters
) {
    (void)raw_futex_call(
        value, FUTEX_WAKE_PRIVATE, (unsigned int)maximum_waiters
    );
}
#endif

#if DEFINE_USES_RAW_CLONE
static void futex_wait_for_thread_exit(
    const atomic_int *thread_id, int expected
) {
    (void)raw_futex_call(thread_id, FUTEX_WAIT, (unsigned int)expected);
}
#endif

static unsigned int work_amount_for(
    const Runtime *runtime, size_t worker_index, size_t execution_index
) {
    const BenchmarkParameters *parameters = &runtime->parameters;
    if (parameters->slow_worker_count == 0) {
        return parameters->fast_work_amount;
    }
    size_t first_slow_worker = execution_index % parameters->active_worker_count;
    size_t distance = (
        worker_index + parameters->active_worker_count - first_slow_worker
    ) % parameters->active_worker_count;
    if (distance < parameters->slow_worker_count) {
        return parameters->slow_work_amount;
    }
    return parameters->fast_work_amount;
}

[[gnu::noinline]] static uint64_t run_compute(
    uint64_t state, unsigned int work_amount
) {
    for (unsigned int round = 0; round < work_amount; ++round) {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state += UINT64_C(0x9e3779b97f4a7c15);
    }
    return state;
}

static void execute_worker(
    RuntimeWorker *worker, size_t execution_index
) {
    uint64_t execution_seed = UINT64_C(0xd1b54a32d192ed03)
        * (uint64_t)(execution_index + 1);
    worker->state = run_compute(
        worker->state ^ execution_seed,
        work_amount_for(worker->runtime, worker->index, execution_index)
    );
    ++worker->completed_execution_count;
}

#if DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_DIRECT_SERIAL
static void dispatch_direct_serial_execution(
    Runtime *runtime, size_t execution_index
) {
    for (size_t worker_index = 0;
         worker_index < runtime->parameters.active_worker_count;
         ++worker_index) {
        execute_worker(&runtime->workers[worker_index], execution_index);
    }
}
#endif

#if DEFINE_USES_PERSISTENT_WORKERS
static unsigned int await_generation(
    RuntimeWorker *worker, unsigned int previous_generation
) {
    const BenchmarkParameters *parameters = &worker->runtime->parameters;
#if DEFINE_USES_TARGETED_PUBLICATION
    atomic_uint *generation_value = &worker->requested_generation;
#else
    atomic_uint *generation_value = &worker->runtime->generation;
#endif
    for (;;) {
        for (unsigned int spin = 0;
             spin < parameters->worker_spin_count;
            ++spin) {
            unsigned int generation = atomic_load_explicit(
                generation_value, memory_order_acquire
            ) & COUNTER_VALUE_MASK;
            if (generation != previous_generation) {
                return generation;
            }
            processor_relax();
        }
#if DEFINE_USES_FUTEX_PARKING
#if DEFINE_GENERATION_WAKE == DEFINE_FUTEX_WAKE_WAITER_BIT
        unsigned int previous_value = atomic_fetch_or_explicit(
            generation_value, COUNTER_WAITER_BIT, memory_order_acq_rel
        );
        if ((previous_value & COUNTER_VALUE_MASK) == previous_generation) {
            futex_wait_private(
                generation_value, previous_value | COUNTER_WAITER_BIT
            );
        }
#else
        futex_wait_private(generation_value, previous_generation);
#endif
#else
        processor_relax();
#endif
        unsigned int generation = atomic_load_explicit(
            generation_value, memory_order_acquire
        ) & COUNTER_VALUE_MASK;
        if (generation != previous_generation) {
            return generation;
        }
    }
}

[[gnu::noinline, gnu::used]] int raw_runtime_worker_main(
    RuntimeWorker *worker
) {
    Runtime *runtime = worker->runtime;
    atomic_fetch_add_explicit(&runtime->ready_workers, 1, memory_order_release);
#if DEFINE_USES_TARGETED_PUBLICATION
    unsigned int previous_generation = atomic_load_explicit(
        &worker->requested_generation, memory_order_acquire
    ) & COUNTER_VALUE_MASK;
#else
    unsigned int previous_generation = atomic_load_explicit(
        &runtime->generation, memory_order_acquire
    ) & COUNTER_VALUE_MASK;
#endif
    for (;;) {
        unsigned int generation = await_generation(worker, previous_generation);
        if (atomic_load_explicit(&runtime->stopping, memory_order_acquire)) {
            return 0;
        }
        if (worker->index >= runtime->parameters.active_worker_count) {
            previous_generation = generation;
            continue;
        }
        execute_worker(worker, generation - 1);
#if !DEFINE_USES_COMPLETION_FLAGS
        unsigned int previous_completed = atomic_fetch_add_explicit(
            &runtime->completed_workers, 1, memory_order_release
        );
#if DEFINE_USES_FUTEX_PARKING
        if ((previous_completed & COUNTER_VALUE_MASK) + 1
            == runtime->parameters.active_worker_count - 1) {
#if DEFINE_COMPLETION_WAKE == DEFINE_FUTEX_WAKE_WAITER_BIT
            if ((previous_completed & COUNTER_WAITER_BIT) != 0) {
                futex_wake_private(&runtime->completed_workers, 1);
            }
#else
            futex_wake_private(&runtime->completed_workers, 1);
#endif
        }
#else
        (void)previous_completed;
#endif
#else
        atomic_store_explicit(
            &worker->completed_generation, generation, memory_order_release
        );
#endif
        previous_generation = generation;
    }
}

#if DEFINE_USES_PTHREAD
static void *pthread_runtime_worker_main(void *context) {
    RuntimeWorker *worker = context;
    (void)raw_runtime_worker_main(worker);
    return NULL;
}
#endif

#if DEFINE_USES_RAW_CLONE
long raw_clone_start(
    RuntimeWorker *worker, struct clone_args *arguments, size_t argument_size
);

__asm__(
    ".text\n"
    ".type raw_clone_start,@function\n"
    "raw_clone_start:\n"
    "push %r12\n"
    "mov %rdi,%r12\n"
    "mov %rsi,%rdi\n"
    "mov %rdx,%rsi\n"
    "mov $" STRINGIFY(SYS_clone3) ",%eax\n"
    "syscall\n"
    "test %rax,%rax\n"
    "jz 1f\n"
    "pop %r12\n"
    "ret\n"
    "1:\n"
    "mov %r12,%rdi\n"
    "call raw_runtime_worker_main\n"
    "mov %eax,%edi\n"
    "mov $" STRINGIFY(SYS_exit) ",%eax\n"
    "syscall\n"
    "ud2\n"
    ".size raw_clone_start,.-raw_clone_start\n"
);
#endif

static void await_ready_workers(Runtime *runtime) {
    unsigned int required = (unsigned int)runtime->parameters.worker_count - 1;
    while (atomic_load_explicit(&runtime->ready_workers, memory_order_acquire)
           != required) {
        processor_relax();
    }
}

static void publish_generation(
    Runtime *runtime, unsigned int generation, size_t published_worker_count
) {
#if DEFINE_USES_TARGETED_PUBLICATION
    atomic_store_explicit(&runtime->generation, generation, memory_order_relaxed);
    for (size_t worker_index = 1; worker_index < published_worker_count;
         ++worker_index) {
        RuntimeWorker *worker = &runtime->workers[worker_index];
#if DEFINE_USES_FUTEX_PARKING
#if DEFINE_GENERATION_WAKE == DEFINE_FUTEX_WAKE_WAITER_BIT
        unsigned int previous_value = atomic_exchange_explicit(
            &worker->requested_generation, generation, memory_order_acq_rel
        );
        if ((previous_value & COUNTER_WAITER_BIT) != 0) {
            futex_wake_private(&worker->requested_generation, 1);
        }
#else
        atomic_store_explicit(
            &worker->requested_generation, generation, memory_order_release
        );
        futex_wake_private(&worker->requested_generation, 1);
#endif
#else
        atomic_store_explicit(
            &worker->requested_generation, generation, memory_order_release
        );
#endif
    }
#else
    (void)published_worker_count;
#if DEFINE_USES_FUTEX_PARKING
#if DEFINE_GENERATION_WAKE == DEFINE_FUTEX_WAKE_WAITER_BIT
    unsigned int previous_value = atomic_exchange_explicit(
        &runtime->generation, generation, memory_order_acq_rel
    );
    if ((previous_value & COUNTER_WAITER_BIT) != 0) {
        futex_wake_private(&runtime->generation, INT_MAX);
    }
#else
    atomic_store_explicit(
        &runtime->generation, generation, memory_order_release
    );
    futex_wake_private(&runtime->generation, INT_MAX);
#endif
#else
    atomic_store_explicit(
        &runtime->generation, generation, memory_order_release
    );
#endif
#endif
}

static void dispatch_execution(Runtime *runtime, size_t execution_index) {
#if !DEFINE_USES_COMPLETION_FLAGS
    unsigned int background_worker_count =
        (unsigned int)runtime->parameters.active_worker_count - 1;
    atomic_store_explicit(
        &runtime->completed_workers, 0, memory_order_relaxed
    );
#endif
    publish_generation(
        runtime,
        (unsigned int)(execution_index + 1),
        runtime->parameters.active_worker_count
    );
    execute_worker(&runtime->workers[0], execution_index);
#if DEFINE_USES_FUTEX_PARKING && !DEFINE_USES_COMPLETION_FLAGS
    for (;;) {
        if ((atomic_load_explicit(
                 &runtime->completed_workers, memory_order_acquire
             )
             & COUNTER_VALUE_MASK)
            == background_worker_count) {
            break;
        }
        bool completed_during_spin = false;
        for (unsigned int spin = 0;
             spin < runtime->parameters.caller_spin_count;
             ++spin) {
            if ((atomic_load_explicit(
                     &runtime->completed_workers, memory_order_acquire
                 )
                 & COUNTER_VALUE_MASK)
                == background_worker_count) {
                completed_during_spin = true;
                break;
            }
            processor_relax();
        }
        if (completed_during_spin) {
            break;
        }
#if DEFINE_COMPLETION_WAKE == DEFINE_FUTEX_WAKE_WAITER_BIT
        unsigned int previous_completed = atomic_fetch_or_explicit(
            &runtime->completed_workers,
            COUNTER_WAITER_BIT,
            memory_order_acq_rel
        );
        if ((previous_completed & COUNTER_VALUE_MASK)
            != background_worker_count) {
            futex_wait_private(
                &runtime->completed_workers,
                previous_completed | COUNTER_WAITER_BIT
            );
        }
#else
        unsigned int previous_completed = atomic_load_explicit(
            &runtime->completed_workers, memory_order_acquire
        );
        if ((previous_completed & COUNTER_VALUE_MASK)
            != background_worker_count) {
            futex_wait_private(&runtime->completed_workers, previous_completed);
        }
#endif
    }
#elif DEFINE_USES_COMPLETION_FLAGS
    unsigned int generation = (unsigned int)(execution_index + 1);
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.active_worker_count;
         ++worker_index) {
        while (atomic_load_explicit(
                   &runtime->workers[worker_index].completed_generation,
                   memory_order_acquire
               )
               != generation) {
            processor_relax();
        }
    }
#else
    while (atomic_load_explicit(
               &runtime->completed_workers, memory_order_acquire
           )
           != background_worker_count) {
        processor_relax();
    }
#endif
}
#endif

static void initialize_worker_state(Runtime *runtime) {
    for (size_t worker_index = 0;
         worker_index < runtime->parameters.worker_count;
         ++worker_index) {
        RuntimeWorker *worker = &runtime->workers[worker_index];
        worker->runtime = runtime;
        worker->index = worker_index;
        worker->state = UINT64_C(0xa0761d6478bd642f) ^ (uint64_t)worker_index;
        worker->completed_execution_count = 0;
#if DEFINE_USES_COMPLETION_FLAGS
        atomic_init(&worker->completed_generation, 0);
#endif
#if DEFINE_USES_TARGETED_PUBLICATION
        atomic_init(&worker->requested_generation, 0);
#endif
    }
}

#if DEFINE_USES_PTHREAD
static void initialize_pthread_attribute(
    pthread_attr_t *attribute, int processor_id
) {
    int error_number = pthread_attr_init(attribute);
    if (error_number != 0) {
        fail_errno("pthread_attr_init", error_number);
    }
    error_number = pthread_attr_setstacksize(attribute, worker_stack_size);
    if (error_number != 0) {
        fail_errno("pthread_attr_setstacksize", error_number);
    }
    cpu_set_t processor_set;
    CPU_ZERO(&processor_set);
    CPU_SET(processor_id, &processor_set);
    error_number = pthread_attr_setaffinity_np(
        attribute, sizeof(processor_set), &processor_set
    );
    if (error_number != 0) {
        fail_errno("pthread_attr_setaffinity_np", error_number);
    }
}
#endif

#if DEFINE_USES_PERSISTENT_WORKERS
static void initialize_persistent_runtime(Runtime *runtime) {
    atomic_init(&runtime->generation, 0);
    atomic_init(&runtime->completed_workers, 0);
    atomic_init(&runtime->ready_workers, 0);
    atomic_init(&runtime->stopping, false);
#if DEFINE_USES_PTHREAD
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.worker_count;
         ++worker_index) {
        pthread_attr_t attribute;
        initialize_pthread_attribute(
            &attribute, runtime->parameters.processor_ids[worker_index]
        );
        int error_number = pthread_create(
            &runtime->workers[worker_index].thread,
            &attribute,
            pthread_runtime_worker_main,
            &runtime->workers[worker_index]
        );
        if (error_number != 0) {
            fail_errno("pthread_create", error_number);
        }
        error_number = pthread_attr_destroy(&attribute);
        if (error_number != 0) {
            fail_errno("pthread_attr_destroy", error_number);
        }
    }
#elif DEFINE_USES_RAW_CLONE
    sigset_t blocked_signals;
    sigset_t previous_signals;
    if (sigfillset(&blocked_signals) != 0
        || sigprocmask(SIG_BLOCK, &blocked_signals, &previous_signals) != 0) {
        fail_errno("sigprocmask", errno);
    }
    size_t stack_size = worker_stack_size;
#if DEFINE_RAW_STACK == DEFINE_RAW_STACK_MAPPED_GUARDED
    long page_size_result = sysconf(_SC_PAGESIZE);
    if (page_size_result <= 0) {
        fail_message("sysconf returned an invalid page size");
    }
    size_t guard_size = (size_t)page_size_result;
#else
    size_t guard_size = 0;
#endif
    size_t stack_stride = guard_size + stack_size;
#if DEFINE_RAW_STACK == DEFINE_RAW_STACK_STATIC
    runtime->stack_arena = raw_worker_stacks;
    runtime->stack_arena_size = 0;
#else
    runtime->stack_arena_size = stack_stride
        * (runtime->parameters.worker_count - 1);
    if (runtime->stack_arena_size != 0) {
        runtime->stack_arena = mmap(
            NULL,
            runtime->stack_arena_size,
            PROT_READ | PROT_WRITE,
            MAP_PRIVATE | MAP_ANONYMOUS | MAP_STACK,
            -1,
            0
        );
        if (runtime->stack_arena == MAP_FAILED) {
            fail_errno("mmap", errno);
        }
    }
#endif
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.worker_count;
         ++worker_index) {
        RuntimeWorker *worker = &runtime->workers[worker_index];
        unsigned char *const stack_region =
            (unsigned char *)runtime->stack_arena
            + stack_stride * (worker_index - 1);
#if DEFINE_RAW_STACK == DEFINE_RAW_STACK_MAPPED_GUARDED
        if (mprotect(stack_region, guard_size, PROT_NONE) != 0) {
            fail_errno("mprotect", errno);
        }
#endif
        atomic_init(&worker->child_tid, 0);
        struct clone_args arguments = {
            .flags = CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND
                | CLONE_THREAD | CLONE_SYSVSEM | CLONE_CHILD_SETTID
                | CLONE_CHILD_CLEARTID,
            .child_tid = (uint64_t)(uintptr_t)&worker->child_tid,
            .stack = (uint64_t)(uintptr_t)stack_region + guard_size,
            .stack_size = stack_size,
        };
        long clone_result = raw_clone_start(
            worker, &arguments, sizeof(arguments)
        );
        if (clone_result < 0) {
            fail_errno("clone3", (int)-clone_result);
        }
        worker->kernel_tid = (int)clone_result;
        cpu_set_t processor_set;
        CPU_ZERO(&processor_set);
        CPU_SET(runtime->parameters.processor_ids[worker_index], &processor_set);
        if (sched_setaffinity(
                worker->kernel_tid, sizeof(processor_set), &processor_set
            )
            != 0) {
            fail_errno("sched_setaffinity", errno);
        }
    }
    if (sigprocmask(SIG_SETMASK, &previous_signals, NULL) != 0) {
        fail_errno("sigprocmask", errno);
    }
#endif
    await_ready_workers(runtime);
}

static void destroy_persistent_runtime(Runtime *runtime) {
    atomic_store_explicit(&runtime->stopping, true, memory_order_release);
    unsigned int generation = atomic_load_explicit(
        &runtime->generation, memory_order_relaxed
    ) & COUNTER_VALUE_MASK;
    publish_generation(runtime, generation + 1, runtime->parameters.worker_count);
#if DEFINE_USES_PTHREAD
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.worker_count;
         ++worker_index) {
        int error_number = pthread_join(
            runtime->workers[worker_index].thread, NULL
        );
        if (error_number != 0) {
            fail_errno("pthread_join", error_number);
        }
    }
#elif DEFINE_USES_RAW_CLONE
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.worker_count;
         ++worker_index) {
        RuntimeWorker *worker = &runtime->workers[worker_index];
        int child_tid = atomic_load_explicit(
            &worker->child_tid, memory_order_acquire
        );
        while (child_tid != 0) {
            futex_wait_for_thread_exit(&worker->child_tid, child_tid);
            child_tid = atomic_load_explicit(
                &worker->child_tid, memory_order_acquire
            );
        }
    }
    if (runtime->stack_arena_size != 0
        && munmap(runtime->stack_arena, runtime->stack_arena_size) != 0) {
        fail_errno("munmap", errno);
    }
#endif
}
#endif

#if DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_FRESH_PTHREAD
typedef struct {
    RuntimeWorker *worker;
    size_t execution_index;
} FreshPthreadArgument;

static void *fresh_pthread_main(void *context) {
    FreshPthreadArgument *argument = context;
    execute_worker(argument->worker, argument->execution_index);
    return NULL;
}

static void initialize_fresh_pthread_runtime(Runtime *runtime) {
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.active_worker_count;
         ++worker_index) {
        initialize_pthread_attribute(
            &runtime->attributes[worker_index],
            runtime->parameters.processor_ids[worker_index]
        );
    }
}

static void dispatch_fresh_pthread_execution(
    Runtime *runtime, size_t execution_index
) {
    pthread_t threads[maximum_workers];
    FreshPthreadArgument arguments[maximum_workers];
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.active_worker_count;
         ++worker_index) {
        arguments[worker_index] = (FreshPthreadArgument){
            .worker = &runtime->workers[worker_index],
            .execution_index = execution_index,
        };
        int error_number = pthread_create(
            &threads[worker_index],
            &runtime->attributes[worker_index],
            fresh_pthread_main,
            &arguments[worker_index]
        );
        if (error_number != 0) {
            fail_errno("pthread_create", error_number);
        }
    }
    execute_worker(&runtime->workers[0], execution_index);
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.active_worker_count;
         ++worker_index) {
        int error_number = pthread_join(threads[worker_index], NULL);
        if (error_number != 0) {
            fail_errno("pthread_join", error_number);
        }
    }
}

static void destroy_fresh_pthread_runtime(Runtime *runtime) {
    for (size_t worker_index = 1;
         worker_index < runtime->parameters.active_worker_count;
         ++worker_index) {
        int error_number = pthread_attr_destroy(
            &runtime->attributes[worker_index]
        );
        if (error_number != 0) {
            fail_errno("pthread_attr_destroy", error_number);
        }
    }
}
#endif

static uint64_t runtime_checksum(const Runtime *runtime) {
    uint64_t checksum = 0;
    size_t expected_execution_count = runtime->parameters.warmup_count
        + runtime->parameters.execution_count;
    for (size_t worker_index = 0;
         worker_index < runtime->parameters.worker_count;
         ++worker_index) {
        const RuntimeWorker *worker = &runtime->workers[worker_index];
        size_t expected_worker_execution_count = worker_index
                < runtime->parameters.active_worker_count
            ? expected_execution_count
            : 0;
        if (worker->completed_execution_count
            != expected_worker_execution_count) {
            fail_message("a worker did not execute exactly once per Action Execution");
        }
        checksum ^= worker->state
            + UINT64_C(0x9e3779b97f4a7c15) * (uint64_t)(worker_index + 1);
    }
    return checksum;
}

static BenchmarkSample run_sample(const BenchmarkParameters *parameters) {
    Runtime *runtime = aligned_alloc(cache_line_size, sizeof(*runtime));
    if (runtime == NULL) {
        fail_errno("aligned_alloc", errno);
    }
    memset(runtime, 0, sizeof(*runtime));
    runtime->parameters = *parameters;
    initialize_worker_state(runtime);

    uint64_t startup_start = read_nanoseconds();
#if DEFINE_USES_PERSISTENT_WORKERS
    initialize_persistent_runtime(runtime);
#elif DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_FRESH_PTHREAD
    initialize_fresh_pthread_runtime(runtime);
#endif
    uint64_t startup_end = read_nanoseconds();

    for (size_t execution_index = 0;
         execution_index < parameters->warmup_count;
         ++execution_index) {
#if DEFINE_USES_PERSISTENT_WORKERS
        dispatch_execution(runtime, execution_index);
#elif DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_FRESH_PTHREAD
        dispatch_fresh_pthread_execution(runtime, execution_index);
#else
        dispatch_direct_serial_execution(runtime, execution_index);
#endif
    }

    uint64_t processor_start = read_processor_nanoseconds();
    uint64_t execution_start = read_nanoseconds();
    uint64_t idle_nanoseconds = 0;
    for (size_t execution_offset = 0;
         execution_offset < parameters->execution_count;
         ++execution_offset) {
        idle_nanoseconds += idle_before_execution(parameters->idle_microseconds);
        size_t execution_index = parameters->warmup_count + execution_offset;
#if DEFINE_USES_PERSISTENT_WORKERS
        dispatch_execution(runtime, execution_index);
#elif DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_FRESH_PTHREAD
        dispatch_fresh_pthread_execution(runtime, execution_index);
#else
        dispatch_direct_serial_execution(runtime, execution_index);
#endif
    }
    uint64_t execution_end = read_nanoseconds();
    uint64_t processor_end = read_processor_nanoseconds();

    uint64_t shutdown_start = read_nanoseconds();
#if DEFINE_USES_PERSISTENT_WORKERS
    destroy_persistent_runtime(runtime);
#elif DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_FRESH_PTHREAD
    destroy_fresh_pthread_runtime(runtime);
#endif
    uint64_t shutdown_end = read_nanoseconds();

    uint64_t checksum = runtime_checksum(runtime);
    free(runtime);
    return (BenchmarkSample){
        .startup_nanoseconds = startup_end - startup_start,
        .execution_nanoseconds = execution_end - execution_start - idle_nanoseconds,
        .processor_nanoseconds = processor_end - processor_start,
        .shutdown_nanoseconds = shutdown_end - shutdown_start,
        .checksum = checksum,
    };
}

static int compare_uint64(const void *left, const void *right) {
    uint64_t left_value = *(const uint64_t *)left;
    uint64_t right_value = *(const uint64_t *)right;
    return (left_value > right_value) - (left_value < right_value);
}

static uint64_t median(uint64_t *values, size_t count) {
    qsort(values, count, sizeof(*values), compare_uint64);
    return values[count / 2];
}

static const char *runtime_name(void) {
#if DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_FRESH_PTHREAD
    return "fresh-pthread";
#elif DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_PTHREAD_SPIN
#if DEFINE_COMPLETION == DEFINE_COMPLETION_FLAGS
    return "pthread-spin-flags";
#else
    return "pthread-spin";
#endif
#elif DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_PTHREAD_FUTEX
#if DEFINE_COMPLETION == DEFINE_COMPLETION_FLAGS
    return "pthread-futex-flags";
#else
    return "pthread-futex";
#endif
#elif DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_CLONE_SPIN
#if DEFINE_COMPLETION == DEFINE_COMPLETION_FLAGS
    return "clone-spin-flags";
#else
    return "clone-spin";
#endif
#elif DEFINE_THREAD_RUNTIME == DEFINE_THREAD_RUNTIME_CLONE_FUTEX
#if DEFINE_COMPLETION == DEFINE_COMPLETION_FLAGS
    return "clone-futex-flags";
#else
    return "clone-futex";
#endif
#else
    return "direct-serial";
#endif
}

static const char *publication_name(void) {
#if !DEFINE_USES_PERSISTENT_WORKERS
    return "none";
#elif DEFINE_USES_TARGETED_PUBLICATION
    return "targeted";
#else
    return "broadcast";
#endif
}

static const char *completion_name(void) {
#if !DEFINE_USES_PERSISTENT_WORKERS
    return "none";
#elif DEFINE_USES_COMPLETION_FLAGS
    return "flags";
#else
    return "counter";
#endif
}

static const char *stack_name(void) {
#if !DEFINE_USES_RAW_CLONE
    return "runtime";
#elif DEFINE_RAW_STACK == DEFINE_RAW_STACK_MAPPED_GUARDED
    return "mapped-guarded";
#elif DEFINE_RAW_STACK == DEFINE_RAW_STACK_MAPPED
    return "mapped";
#else
    return "static";
#endif
}

static const char *generation_wake_name(void) {
#if !DEFINE_USES_FUTEX_PARKING
    return "none";
#elif DEFINE_GENERATION_WAKE == DEFINE_FUTEX_WAKE_WAITER_BIT
    return "waiter-bit";
#else
    return "unconditional";
#endif
}

static const char *completion_wake_name(void) {
#if !DEFINE_USES_FUTEX_PARKING
    return "none";
#elif DEFINE_COMPLETION_WAKE == DEFINE_FUTEX_WAKE_WAITER_BIT
    return "waiter-bit";
#else
    return "unconditional";
#endif
}

static BenchmarkParameters parse_parameters(int argument_count, char **arguments) {
    if (argument_count != 12) {
        fprintf(
            stderr,
            "usage: %s workers active-workers executions fast-work slow-work "
            "slow-workers "
            "idle-microseconds worker-spin caller-spin warmups samples\n",
            arguments[0]
        );
        exit(EXIT_FAILURE);
    }
    BenchmarkParameters parameters = {
        .worker_count = parse_size(arguments[1], "worker count"),
        .active_worker_count = parse_size(arguments[2], "active worker count"),
        .execution_count = parse_size(arguments[3], "execution count"),
        .fast_work_amount = parse_unsigned(arguments[4], "fast work"),
        .slow_work_amount = parse_unsigned(arguments[5], "slow work"),
        .slow_worker_count = parse_size(arguments[6], "slow worker count"),
        .idle_microseconds = parse_unsigned(arguments[7], "idle microseconds"),
        .worker_spin_count = parse_unsigned(arguments[8], "worker spin count"),
        .caller_spin_count = parse_unsigned(arguments[9], "caller spin count"),
        .warmup_count = parse_size(arguments[10], "warmup count"),
        .sample_count = parse_size(arguments[11], "sample count"),
    };
    if (parameters.worker_count == 0
        || parameters.worker_count > maximum_workers) {
        fail_message("worker count must be between 1 and 32");
    }
    if (parameters.active_worker_count == 0
        || parameters.active_worker_count > parameters.worker_count) {
        fail_message("active worker count must be between 1 and worker count");
    }
    if (parameters.execution_count == 0 || parameters.sample_count == 0) {
        fail_message("execution count and sample count must be positive");
    }
    if (parameters.warmup_count > COUNTER_VALUE_MASK
        || parameters.execution_count
            > COUNTER_VALUE_MASK - parameters.warmup_count) {
        fail_message("warmup and timed executions exceed the generation range");
    }
    if (parameters.slow_worker_count > parameters.active_worker_count) {
        fail_message("slow worker count cannot exceed active worker count");
    }
    cpu_set_t available_processors;
    if (sched_getaffinity(0, sizeof(available_processors), &available_processors)
        != 0) {
        fail_errno("sched_getaffinity", errno);
    }
    size_t discovered_processor_count = 0;
    for (int processor_id = 0;
         processor_id < CPU_SETSIZE
         && discovered_processor_count < parameters.worker_count;
         ++processor_id) {
        if (CPU_ISSET(processor_id, &available_processors)) {
            parameters.processor_ids[discovered_processor_count] = processor_id;
            ++discovered_processor_count;
        }
    }
    if (discovered_processor_count != parameters.worker_count) {
        fail_message("not enough processors are available for the requested workers");
    }
    cpu_set_t caller_processor;
    CPU_ZERO(&caller_processor);
    CPU_SET(parameters.processor_ids[0], &caller_processor);
    if (sched_setaffinity(0, sizeof(caller_processor), &caller_processor) != 0) {
        fail_errno("sched_setaffinity", errno);
    }
    return parameters;
}

int main(int argument_count, char **arguments) {
    BenchmarkParameters parameters = parse_parameters(argument_count, arguments);
    uint64_t *startup_samples = calloc(
        parameters.sample_count, sizeof(*startup_samples)
    );
    uint64_t *execution_samples = calloc(
        parameters.sample_count, sizeof(*execution_samples)
    );
    uint64_t *processor_samples = calloc(
        parameters.sample_count, sizeof(*processor_samples)
    );
    uint64_t *shutdown_samples = calloc(
        parameters.sample_count, sizeof(*shutdown_samples)
    );
    uint64_t *amortized_samples = calloc(
        parameters.sample_count, sizeof(*amortized_samples)
    );
    if (startup_samples == NULL || execution_samples == NULL
        || processor_samples == NULL
        || shutdown_samples == NULL || amortized_samples == NULL) {
        fail_errno("calloc", errno);
    }

    uint64_t expected_checksum = 0;
    for (size_t sample_index = 0; sample_index < parameters.sample_count;
         ++sample_index) {
        BenchmarkSample sample = run_sample(&parameters);
        if (sample_index == 0) {
            expected_checksum = sample.checksum;
        } else if (sample.checksum != expected_checksum) {
            fail_message("sample checksums differ");
        }
        startup_samples[sample_index] = sample.startup_nanoseconds;
        execution_samples[sample_index] = sample.execution_nanoseconds
            / parameters.execution_count;
        processor_samples[sample_index] = sample.processor_nanoseconds
            / parameters.execution_count;
        shutdown_samples[sample_index] = sample.shutdown_nanoseconds;
        amortized_samples[sample_index] = (
            sample.startup_nanoseconds + sample.execution_nanoseconds
            + sample.shutdown_nanoseconds
        ) / parameters.execution_count;
    }

    printf(
        "runtime=%s publication=%s completion=%s stack=%s "
        "generation_wake=%s completion_wake=%s workers=%zu active=%zu "
        "executions=%zu fast_work=%u slow_work=%u "
        "slow_workers=%zu idle_us=%u worker_spin=%u caller_spin=%u "
        "startup_ns=%" PRIu64
        " execution_ns=%" PRIu64 " processor_ns=%" PRIu64
        " shutdown_ns=%" PRIu64
        " amortized_ns=%" PRIu64 " checksum=%" PRIu64 "\n",
        runtime_name(),
        publication_name(),
        completion_name(),
        stack_name(),
        generation_wake_name(),
        completion_wake_name(),
        parameters.worker_count,
        parameters.active_worker_count,
        parameters.execution_count,
        parameters.fast_work_amount,
        parameters.slow_work_amount,
        parameters.slow_worker_count,
        parameters.idle_microseconds,
        parameters.worker_spin_count,
        parameters.caller_spin_count,
        median(startup_samples, parameters.sample_count),
        median(execution_samples, parameters.sample_count),
        median(processor_samples, parameters.sample_count),
        median(shutdown_samples, parameters.sample_count),
        median(amortized_samples, parameters.sample_count),
        expected_checksum
    );

    free(amortized_samples);
    free(shutdown_samples);
    free(processor_samples);
    free(execution_samples);
    free(startup_samples);
    return EXIT_SUCCESS;
}
