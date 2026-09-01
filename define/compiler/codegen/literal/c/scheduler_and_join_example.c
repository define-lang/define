#define _GNU_SOURCE

#if !defined(__linux__)
#error "scheduler_and_join_example.c requires Linux target runtime facilities"
#endif

#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(__x86_64__) || defined(__i386__)
#include <immintrin.h>
#endif

#if !defined(LITERAL_QUEUE_CAPACITY)
#define LITERAL_QUEUE_CAPACITY 65536
#endif

#if !defined(LITERAL_MAXIMUM_WORKERS)
#define LITERAL_MAXIMUM_WORKERS 32
#endif

#if !defined(LITERAL_SINGLE_TOPOLOGY_GROUP)
#define LITERAL_SINGLE_TOPOLOGY_GROUP 0
#endif

#if !defined(LITERAL_TWO_SINGLE_WORKER_GROUPS)
#define LITERAL_TWO_SINGLE_WORKER_GROUPS 0
#endif

#if !defined(LITERAL_PROVEN_DEQUE_CAPACITY)
#define LITERAL_PROVEN_DEQUE_CAPACITY 0
#endif

#if !defined(LITERAL_SHARED_VICTIM_LISTS)
#define LITERAL_SHARED_VICTIM_LISTS 1
#endif

#if !defined(LITERAL_PROVEN_BOUNDED_SPMC_INJECTION)
#define LITERAL_PROVEN_BOUNDED_SPMC_INJECTION 0
#endif

#if !defined(LITERAL_STEAL_BATCH_SIZE)
#define LITERAL_STEAL_BATCH_SIZE 1
#endif

#if !defined(LITERAL_INJECTION_BATCH_SIZE)
#define LITERAL_INJECTION_BATCH_SIZE 1
#endif

#if LITERAL_SINGLE_TOPOLOGY_GROUP && LITERAL_TWO_SINGLE_WORKER_GROUPS
#error "the generated topology specializations are mutually exclusive"
#endif

#if LITERAL_STEAL_BATCH_SIZE < 1 || LITERAL_INJECTION_BATCH_SIZE < 1
#error "scheduler batch sizes must be positive"
#endif

#if LITERAL_INJECTION_BATCH_SIZE > 1 \
    && !LITERAL_PROVEN_BOUNDED_SPMC_INJECTION
#error "batch injection requires a proven single producer and total bound"
#endif

enum {
    example_cache_line_alignment = 64,
    example_maximum_topology_groups = 2,
    example_maximum_workers = LITERAL_MAXIMUM_WORKERS,
    example_queue_capacity = LITERAL_QUEUE_CAPACITY,
};

_Static_assert(
    example_queue_capacity > 0
        && (example_queue_capacity & (example_queue_capacity - 1)) == 0,
    "the scheduler queue capacity must be a positive power of two"
);

typedef struct LiteralScheduler LiteralScheduler;
typedef struct LiteralSchedulerTask LiteralSchedulerTask;
typedef struct LiteralSchedulerWorker LiteralSchedulerWorker;

typedef LiteralSchedulerTask *(*LiteralSchedulerTaskFunction)(
    LiteralSchedulerWorker *, LiteralSchedulerTask *
);

struct LiteralSchedulerTask {
    LiteralSchedulerTaskFunction function;
    void *context;
    uint16_t preferred_group;
};

typedef struct {
    atomic_size_t sequence;
    LiteralSchedulerTask *task;
} InjectionQueueCell;

typedef struct {
    alignas(example_cache_line_alignment) atomic_size_t enqueue_position;
    unsigned char enqueue_padding[
        example_cache_line_alignment - sizeof(atomic_size_t)
    ];
    alignas(example_cache_line_alignment) atomic_size_t dequeue_position;
    unsigned char dequeue_padding[
        example_cache_line_alignment - sizeof(atomic_size_t)
    ];
#if LITERAL_PROVEN_BOUNDED_SPMC_INJECTION
    LiteralSchedulerTask **tasks;
#else
    InjectionQueueCell *cells;
#endif
    size_t mask;
} InjectionQueue;

typedef struct {
    alignas(example_cache_line_alignment) atomic_int_fast64_t top;
    unsigned char top_padding[
        example_cache_line_alignment - sizeof(atomic_int_fast64_t)
    ];
    alignas(example_cache_line_alignment) atomic_int_fast64_t bottom;
    unsigned char bottom_padding[
        example_cache_line_alignment - sizeof(atomic_int_fast64_t)
    ];
    _Atomic(LiteralSchedulerTask *) *tasks;
    int64_t mask;
} WorkDeque;

typedef struct {
    alignas(example_cache_line_alignment) atomic_bool value;
    unsigned char padding[example_cache_line_alignment - sizeof(atomic_bool)];
} PaddedBoolean;

typedef struct {
    alignas(example_cache_line_alignment) atomic_uint remaining;
    unsigned char padding[example_cache_line_alignment - sizeof(atomic_uint)];
} LiteralJoin;

typedef struct {
    size_t worker_count;
    size_t group_count;
    int processor_ids[example_maximum_workers];
    uint16_t group_ids[example_maximum_workers];
    unsigned int cross_group_poll_delay;
} LiteralSchedulerConfig;

struct LiteralSchedulerWorker {
    WorkDeque deque;
    LiteralScheduler *scheduler;
#if LITERAL_TWO_SINGLE_WORKER_GROUPS
    size_t index;
#endif
#if LITERAL_SHARED_VICTIM_LISTS && !LITERAL_TWO_SINGLE_WORKER_GROUPS
    size_t same_group_victim_cursor;
    size_t cross_group_victim_cursor;
    size_t group_member_position;
#elif !LITERAL_TWO_SINGLE_WORKER_GROUPS
    uint64_t random_state;
#endif
    int processor_id;
#if !LITERAL_SINGLE_TOPOLOGY_GROUP
    unsigned int failed_local_polls;
#endif
    uint16_t group;
};

struct LiteralScheduler {
    size_t worker_count;
    size_t group_count;
    LiteralSchedulerWorker workers[example_maximum_workers];
#if !LITERAL_SINGLE_TOPOLOGY_GROUP
    InjectionQueue group_injection[example_maximum_topology_groups];
#endif
#if LITERAL_SHARED_VICTIM_LISTS && !LITERAL_TWO_SINGLE_WORKER_GROUPS
    LiteralSchedulerWorker *group_workers[example_maximum_topology_groups][
        example_maximum_workers
    ];
    size_t group_worker_counts[example_maximum_topology_groups];
#endif
    PaddedBoolean done;
#if !LITERAL_SINGLE_TOPOLOGY_GROUP
    unsigned int cross_group_poll_delay;
#endif
};

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

static void require_lock_free_scheduler_atomics(void) {
    atomic_bool completion_state;
    atomic_uint join_counter;
    atomic_size_t queue_position;
    atomic_int_fast64_t deque_position;
    _Atomic(LiteralSchedulerTask *) task_pointer;
    atomic_init(&completion_state, false);
    atomic_init(&join_counter, 0);
    atomic_init(&queue_position, 0);
    atomic_init(&deque_position, 0);
    atomic_init(&task_pointer, NULL);
    if (!atomic_is_lock_free(&completion_state)
        || !atomic_is_lock_free(&join_counter)
        || !atomic_is_lock_free(&queue_position)
        || !atomic_is_lock_free(&deque_position)
        || !atomic_is_lock_free(&task_pointer)) {
        fail_message("the scheduler example requires lock-free C atomics");
    }
}

static void *allocate_aligned(size_t alignment, size_t size) {
    void *allocation = NULL;
    int error_number = posix_memalign(&allocation, alignment, size);
    if (error_number != 0) {
        fail_errno("posix_memalign", error_number);
    }
    memset(allocation, 0, size);
    return allocation;
}

static void processor_relax(void) {
#if defined(__x86_64__) || defined(__i386__)
    _mm_pause();
#else
    atomic_signal_fence(memory_order_seq_cst);
#endif
}

static void pin_current_thread(int processor_id) {
    if (processor_id < 0) {
        return;
    }
    cpu_set_t processor_set;
    CPU_ZERO(&processor_set);
    CPU_SET((size_t)processor_id, &processor_set);
    int error_number = pthread_setaffinity_np(
        pthread_self(), sizeof(processor_set), &processor_set
    );
    if (error_number != 0) {
        fail_errno("pthread_setaffinity_np", error_number);
    }
}

[[maybe_unused]] static void initialize_injection_queue(InjectionQueue *queue) {
    queue->mask = example_queue_capacity - 1;
#if LITERAL_PROVEN_BOUNDED_SPMC_INJECTION
    queue->tasks = allocate_aligned(
        example_cache_line_alignment,
        example_queue_capacity * sizeof(*queue->tasks)
    );
#else
    queue->cells = allocate_aligned(
        example_cache_line_alignment,
        example_queue_capacity * sizeof(*queue->cells)
    );
    for (size_t position = 0; position < example_queue_capacity; ++position) {
        atomic_init(&queue->cells[position].sequence, position);
    }
#endif
    atomic_init(&queue->enqueue_position, 0);
    atomic_init(&queue->dequeue_position, 0);
}

[[maybe_unused]] static void destroy_injection_queue(InjectionQueue *queue) {
#if LITERAL_PROVEN_BOUNDED_SPMC_INJECTION
    free(queue->tasks);
#else
    free(queue->cells);
#endif
}

[[maybe_unused]] static bool try_enqueue_injection(
    InjectionQueue *queue, LiteralSchedulerTask *task
) {
    size_t position = atomic_load_explicit(
        &queue->enqueue_position, memory_order_relaxed
    );
#if LITERAL_PROVEN_BOUNDED_SPMC_INJECTION
    queue->tasks[position & queue->mask] = task;
    atomic_store_explicit(
        &queue->enqueue_position, position + 1, memory_order_release
    );
    return true;
#else
    InjectionQueueCell *cell;
    for (;;) {
        cell = &queue->cells[position & queue->mask];
        size_t sequence = atomic_load_explicit(&cell->sequence, memory_order_acquire);
        intptr_t difference = (intptr_t)sequence - (intptr_t)position;
        if (difference == 0) {
            if (atomic_compare_exchange_weak_explicit(
                    &queue->enqueue_position,
                    &position,
                    position + 1,
                    memory_order_relaxed,
                    memory_order_relaxed
                )) {
                break;
            }
        } else if (difference < 0) {
            return false;
        } else {
            position = atomic_load_explicit(
                &queue->enqueue_position, memory_order_relaxed
            );
        }
    }
    cell->task = task;
    atomic_store_explicit(&cell->sequence, position + 1, memory_order_release);
    return true;
#endif
}

[[maybe_unused]] static LiteralSchedulerTask *try_dequeue_injection(
    InjectionQueue *queue
) {
    size_t position = atomic_load_explicit(
        &queue->dequeue_position, memory_order_relaxed
    );
#if LITERAL_PROVEN_BOUNDED_SPMC_INJECTION
    for (;;) {
        size_t enqueue_position = atomic_load_explicit(
            &queue->enqueue_position, memory_order_acquire
        );
        if (position == enqueue_position) {
            return NULL;
        }
        if (atomic_compare_exchange_weak_explicit(
                &queue->dequeue_position,
                &position,
                position + 1,
                memory_order_relaxed,
                memory_order_relaxed
            )) {
            return queue->tasks[position & queue->mask];
        }
    }
#else
    InjectionQueueCell *cell;
    for (;;) {
        cell = &queue->cells[position & queue->mask];
        size_t sequence = atomic_load_explicit(&cell->sequence, memory_order_acquire);
        intptr_t difference = (intptr_t)sequence - (intptr_t)(position + 1);
        if (difference == 0) {
            if (atomic_compare_exchange_weak_explicit(
                    &queue->dequeue_position,
                    &position,
                    position + 1,
                    memory_order_relaxed,
                    memory_order_relaxed
                )) {
                break;
            }
        } else if (difference < 0) {
            return NULL;
        } else {
            position = atomic_load_explicit(
                &queue->dequeue_position, memory_order_relaxed
            );
        }
    }
    LiteralSchedulerTask *task = cell->task;
    atomic_store_explicit(
        &cell->sequence, position + queue->mask + 1, memory_order_release
    );
    return task;
#endif
}

static void initialize_work_deque(WorkDeque *deque) {
    deque->mask = example_queue_capacity - 1;
    deque->tasks = allocate_aligned(
        example_cache_line_alignment,
        example_queue_capacity * sizeof(*deque->tasks)
    );
    atomic_init(&deque->top, 0);
    atomic_init(&deque->bottom, 0);
}

static void destroy_work_deque(WorkDeque *deque) {
    free(deque->tasks);
}

static void push_work_deque(WorkDeque *deque, LiteralSchedulerTask *task) {
    int64_t bottom = atomic_load_explicit(&deque->bottom, memory_order_relaxed);
#if !LITERAL_PROVEN_DEQUE_CAPACITY
    int64_t top = atomic_load_explicit(&deque->top, memory_order_acquire);
    if (bottom - top >= example_queue_capacity) {
        fail_message("work deque capacity exceeded");
    }
#endif
    atomic_store_explicit(
        &deque->tasks[bottom & deque->mask], task, memory_order_relaxed
    );
    atomic_thread_fence(memory_order_release);
    atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_relaxed);
}

#if LITERAL_STEAL_BATCH_SIZE > 1 || LITERAL_INJECTION_BATCH_SIZE > 1
static void retain_claimed_tasks(
    LiteralSchedulerWorker *worker,
    LiteralSchedulerTask **claimed_tasks,
    size_t claim_count
) {
    if (claim_count == 1) {
        return;
    }
    WorkDeque *deque = &worker->deque;
    int64_t bottom = atomic_load_explicit(
        &deque->bottom, memory_order_relaxed
    );
#if !LITERAL_PROVEN_DEQUE_CAPACITY
    int64_t top = atomic_load_explicit(&deque->top, memory_order_acquire);
    if (bottom - top + (int64_t)claim_count - 1 > example_queue_capacity) {
        fail_message("work deque capacity exceeded by a grouped steal");
    }
#endif
    for (size_t offset = 1; offset < claim_count; ++offset) {
        atomic_store_explicit(
            &deque->tasks[(bottom + (int64_t)offset - 1) & deque->mask],
            claimed_tasks[offset],
            memory_order_relaxed
        );
    }
    atomic_thread_fence(memory_order_release);
    atomic_store_explicit(
        &deque->bottom,
        bottom + (int64_t)claim_count - 1,
        memory_order_relaxed
    );
}
#endif

#if LITERAL_INJECTION_BATCH_SIZE > 1
static LiteralSchedulerTask *dequeue_injection_batch(
    LiteralSchedulerWorker *worker, InjectionQueue *queue
) {
    size_t position = atomic_load_explicit(
        &queue->dequeue_position, memory_order_relaxed
    );
    size_t enqueue_position = atomic_load_explicit(
        &queue->enqueue_position, memory_order_acquire
    );
    if (position == enqueue_position) {
        return NULL;
    }
    size_t claim_count = (enqueue_position - position) / 2;
    if (claim_count == 0) {
        claim_count = 1;
    }
    if (claim_count > LITERAL_INJECTION_BATCH_SIZE) {
        claim_count = LITERAL_INJECTION_BATCH_SIZE;
    }
    LiteralSchedulerTask *claimed_tasks[LITERAL_INJECTION_BATCH_SIZE];
    for (size_t offset = 0; offset < claim_count; ++offset) {
        claimed_tasks[offset] = queue->tasks[
            (position + offset) & queue->mask
        ];
    }
    size_t next_position = position + claim_count;
    if (!atomic_compare_exchange_strong_explicit(
            &queue->dequeue_position,
            &position,
            next_position,
            memory_order_relaxed,
            memory_order_relaxed
        )) {
        return NULL;
    }
    retain_claimed_tasks(worker, claimed_tasks, claim_count);
    return claimed_tasks[0];
}
#endif

[[maybe_unused]] static LiteralSchedulerTask *dequeue_injection_for_worker(
    LiteralSchedulerWorker *worker, InjectionQueue *queue
) {
#if LITERAL_INJECTION_BATCH_SIZE > 1
    return dequeue_injection_batch(worker, queue);
#else
    (void)worker;
    return try_dequeue_injection(queue);
#endif
}

static LiteralSchedulerTask *pop_work_deque(WorkDeque *deque) {
    int64_t bottom = atomic_load_explicit(&deque->bottom, memory_order_relaxed) - 1;
    atomic_store_explicit(&deque->bottom, bottom, memory_order_relaxed);
    atomic_thread_fence(memory_order_seq_cst);
    int64_t top = atomic_load_explicit(&deque->top, memory_order_relaxed);
    if (top <= bottom) {
        LiteralSchedulerTask *task = atomic_load_explicit(
            &deque->tasks[bottom & deque->mask], memory_order_relaxed
        );
        if (top == bottom) {
            int64_t next_top = top + 1;
            if (!atomic_compare_exchange_strong_explicit(
                    &deque->top,
                    &top,
                    next_top,
                    memory_order_seq_cst,
                    memory_order_relaxed
                )) {
                task = NULL;
            }
            atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_relaxed);
        }
        return task;
    }
    atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_relaxed);
    return NULL;
}

static LiteralSchedulerTask *steal_one_work_deque(WorkDeque *victim_deque) {
    int64_t top = atomic_load_explicit(
        &victim_deque->top, memory_order_acquire
    );
#if !defined(__x86_64__) && !defined(__i386__)
    atomic_thread_fence(memory_order_seq_cst);
#endif
    int64_t bottom = atomic_load_explicit(
        &victim_deque->bottom, memory_order_acquire
    );
    if (top >= bottom) {
        return NULL;
    }
    LiteralSchedulerTask *task = atomic_load_explicit(
        &victim_deque->tasks[top & victim_deque->mask], memory_order_relaxed
    );
    int64_t next_top = top + 1;
    if (!atomic_compare_exchange_strong_explicit(
            &victim_deque->top,
            &top,
            next_top,
            memory_order_seq_cst,
            memory_order_relaxed
        )) {
        return NULL;
    }
    return task;
}

static LiteralSchedulerTask *steal_work_deque(
    LiteralSchedulerWorker *thief, WorkDeque *victim_deque
) {
#if LITERAL_STEAL_BATCH_SIZE > 1
    int64_t top = atomic_load_explicit(
        &victim_deque->top, memory_order_acquire
    );
    int64_t bottom = atomic_load_explicit(
        &victim_deque->bottom, memory_order_acquire
    );
    int64_t claim_limit = (bottom - top) / 2;
    if (claim_limit < 1) {
        claim_limit = 1;
    }
    if (claim_limit > LITERAL_STEAL_BATCH_SIZE) {
        claim_limit = LITERAL_STEAL_BATCH_SIZE;
    }
    LiteralSchedulerTask *claimed_tasks[LITERAL_STEAL_BATCH_SIZE];
    size_t claim_count = 0;
    while (claim_count < (size_t)claim_limit) {
        LiteralSchedulerTask *task = steal_one_work_deque(victim_deque);
        if (task == NULL) {
            break;
        }
        claimed_tasks[claim_count++] = task;
    }
    if (claim_count == 0) {
        return NULL;
    }
    retain_claimed_tasks(thief, claimed_tasks, claim_count);
    return claimed_tasks[0];
#else
    (void)thief;
    return steal_one_work_deque(victim_deque);
#endif
}

static void literal_join_initialize(LiteralJoin *join, unsigned int arrivals) {
    atomic_init(&join->remaining, arrivals);
}

static bool literal_join_arrive(LiteralJoin *join) {
    return atomic_fetch_sub_explicit(&join->remaining, 1, memory_order_acq_rel)
        == 1;
}

#if !LITERAL_SHARED_VICTIM_LISTS && !LITERAL_TWO_SINGLE_WORKER_GROUPS
static uint64_t next_random(LiteralSchedulerWorker *worker) {
    uint64_t state = worker->random_state;
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    worker->random_state = state;
    return state;
}
#endif

static void literal_scheduler_submit(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
#if LITERAL_SINGLE_TOPOLOGY_GROUP
    push_work_deque(&worker->deque, task);
#else
    LiteralScheduler *scheduler = worker->scheduler;
    if (task->preferred_group >= scheduler->group_count) {
        fail_message("scheduler task has an invalid preferred topology group");
    }
    if (task->preferred_group != worker->group) {
#if LITERAL_PROVEN_BOUNDED_SPMC_INJECTION
        (void)try_enqueue_injection(
            &scheduler->group_injection[task->preferred_group], task
        );
        return;
#else
        if (try_enqueue_injection(
                &scheduler->group_injection[task->preferred_group], task
            )) {
            return;
        }
#endif
    }
    push_work_deque(&worker->deque, task);
#endif
}

[[maybe_unused]] static bool literal_scheduler_can_continue(
    const LiteralSchedulerWorker *worker,
    const LiteralSchedulerTask *continuation,
    bool prefer_topology_group
) {
#if LITERAL_SINGLE_TOPOLOGY_GROUP
    (void)worker;
    (void)continuation;
    (void)prefer_topology_group;
    return true;
#else
    return !prefer_topology_group || continuation->preferred_group == worker->group;
#endif
}

#if !LITERAL_TWO_SINGLE_WORKER_GROUPS
static LiteralSchedulerTask *try_steal_from_workers(
    LiteralSchedulerWorker *worker, bool same_group
) {
    LiteralScheduler *scheduler = worker->scheduler;
#if LITERAL_SHARED_VICTIM_LISTS
    uint16_t victim_group = worker->group;
    size_t *stored_cursor = &worker->same_group_victim_cursor;
    if (!same_group) {
        if (scheduler->group_count == 1) {
            return NULL;
        }
        victim_group = worker->group == 0 ? 1 : 0;
        stored_cursor = &worker->cross_group_victim_cursor;
    }
    size_t victim_count = scheduler->group_worker_counts[victim_group];
    if (victim_count == 0 || (same_group && victim_count == 1)) {
        return NULL;
    }
    LiteralSchedulerWorker **victims = scheduler->group_workers[victim_group];
    size_t start = *stored_cursor;
    size_t cursor = start;
    for (size_t offset = 0; offset < victim_count; ++offset) {
        LiteralSchedulerWorker *victim = victims[cursor];
        ++cursor;
        if (cursor == victim_count) {
            cursor = 0;
        }
        if (victim == worker) {
            continue;
        }
        LiteralSchedulerTask *task = steal_work_deque(worker, &victim->deque);
        if (task != NULL) {
            *stored_cursor = cursor;
            return task;
        }
    }
    ++start;
    if (start == victim_count) {
        start = 0;
    }
    *stored_cursor = start;
    return NULL;
#else
    size_t start = next_random(worker) % scheduler->worker_count;
    for (size_t offset = 0; offset < scheduler->worker_count; ++offset) {
        size_t victim_index = (start + offset) % scheduler->worker_count;
        LiteralSchedulerWorker *victim = &scheduler->workers[victim_index];
        if (victim == worker) {
            continue;
        }
        if ((victim->group == worker->group) != same_group) {
            continue;
        }
        LiteralSchedulerTask *task = steal_work_deque(worker, &victim->deque);
        if (task != NULL) {
            return task;
        }
    }
    return NULL;
#endif
}
#endif

static LiteralSchedulerTask *next_scheduler_task(LiteralSchedulerWorker *worker) {
#if LITERAL_SINGLE_TOPOLOGY_GROUP
    LiteralSchedulerTask *task = pop_work_deque(&worker->deque);
    if (task != NULL) {
        return task;
    }
    return try_steal_from_workers(worker, true);
#else
    LiteralScheduler *scheduler = worker->scheduler;
    LiteralSchedulerTask *task = pop_work_deque(&worker->deque);
    if (task != NULL) {
        worker->failed_local_polls = 0;
        return task;
    }

    task = dequeue_injection_for_worker(
        worker, &scheduler->group_injection[worker->group]
    );
    if (task != NULL) {
        worker->failed_local_polls = 0;
        return task;
    }

#if !LITERAL_TWO_SINGLE_WORKER_GROUPS
    task = try_steal_from_workers(worker, true);
    if (task != NULL) {
        worker->failed_local_polls = 0;
        return task;
    }
#endif

    if (worker->failed_local_polls < scheduler->cross_group_poll_delay) {
        ++worker->failed_local_polls;
        return NULL;
    }
    worker->failed_local_polls = 0;

#if LITERAL_TWO_SINGLE_WORKER_GROUPS
    uint16_t other_group = worker->group == 0 ? 1 : 0;
    task = dequeue_injection_for_worker(
        worker, &scheduler->group_injection[other_group]
    );
    if (task != NULL) {
        return task;
    }
    LiteralSchedulerWorker *victim = &scheduler->workers[
        worker->index == 0 ? 1 : 0
    ];
    return steal_work_deque(worker, &victim->deque);
#else
    for (size_t group = 0; group < scheduler->group_count; ++group) {
        if (group == worker->group) {
            continue;
        }
        task = dequeue_injection_for_worker(
            worker, &scheduler->group_injection[group]
        );
        if (task != NULL) {
            return task;
        }
    }
    return try_steal_from_workers(worker, false);
#endif
#endif
}

static void *run_scheduler_worker(void *opaque_worker) {
    LiteralSchedulerWorker *worker = opaque_worker;
    LiteralScheduler *scheduler = worker->scheduler;
    pin_current_thread(worker->processor_id);

    LiteralSchedulerTask *task = NULL;
    for (;;) {
        if (task == NULL) {
            if (atomic_load_explicit(&scheduler->done.value, memory_order_acquire)) {
                break;
            }
            task = next_scheduler_task(worker);
            if (task == NULL) {
                processor_relax();
                continue;
            }
        }
        task = task->function(worker, task);
    }
    return NULL;
}

static void literal_scheduler_initialize(
    LiteralScheduler *scheduler, const LiteralSchedulerConfig *config
) {
    if (config->worker_count == 0
        || config->worker_count > example_maximum_workers) {
        fail_message("invalid scheduler worker count");
    }
    if (config->group_count == 0
        || config->group_count > example_maximum_topology_groups
        || config->group_count > config->worker_count) {
        fail_message("invalid scheduler topology group count");
    }
#if LITERAL_SINGLE_TOPOLOGY_GROUP
    if (config->group_count != 1) {
        fail_message("generated scheduler requires one topology group");
    }
#elif LITERAL_TWO_SINGLE_WORKER_GROUPS
    if (config->worker_count != 2 || config->group_count != 2) {
        fail_message("generated scheduler requires two one-worker groups");
    }
#endif

    memset(scheduler, 0, sizeof(*scheduler));
    scheduler->worker_count = config->worker_count;
    scheduler->group_count = config->group_count;
#if !LITERAL_SINGLE_TOPOLOGY_GROUP
    scheduler->cross_group_poll_delay = config->cross_group_poll_delay;
#endif
    atomic_init(&scheduler->done.value, false);

    require_lock_free_scheduler_atomics();

    bool group_has_worker[example_maximum_topology_groups] = {false};
#if !LITERAL_SINGLE_TOPOLOGY_GROUP
    for (size_t group = 0; group < scheduler->group_count; ++group) {
        initialize_injection_queue(&scheduler->group_injection[group]);
    }
#endif
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        uint16_t group = config->group_ids[worker_index];
        if (group >= scheduler->group_count) {
            fail_message("scheduler worker has an invalid topology group");
        }
        group_has_worker[group] = true;
        LiteralSchedulerWorker *worker = &scheduler->workers[worker_index];
        worker->scheduler = scheduler;
#if LITERAL_TWO_SINGLE_WORKER_GROUPS
        worker->index = worker_index;
#endif
        worker->processor_id = config->processor_ids[worker_index];
        worker->group = group;
#if LITERAL_SHARED_VICTIM_LISTS && !LITERAL_TWO_SINGLE_WORKER_GROUPS
        worker->group_member_position = scheduler->group_worker_counts[group];
        scheduler->group_workers[group][
            scheduler->group_worker_counts[group]++
        ] = worker;
#elif !LITERAL_TWO_SINGLE_WORKER_GROUPS
        worker->random_state = UINT64_C(0x2545f4914f6cdd1d)
            ^ (worker_index * UINT64_C(0x9e3779b97f4a7c15));
#endif
        initialize_work_deque(&worker->deque);
    }
    for (size_t group = 0; group < scheduler->group_count; ++group) {
        if (!group_has_worker[group]) {
            fail_message("scheduler topology group has no workers");
        }
    }
#if LITERAL_SHARED_VICTIM_LISTS && !LITERAL_TWO_SINGLE_WORKER_GROUPS
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        LiteralSchedulerWorker *worker = &scheduler->workers[worker_index];
        size_t same_group_count = scheduler->group_worker_counts[worker->group];
        worker->same_group_victim_cursor = worker->group_member_position + 1;
        if (worker->same_group_victim_cursor == same_group_count) {
            worker->same_group_victim_cursor = 0;
        }
        if (scheduler->group_count == 2) {
            uint16_t other_group = worker->group == 0 ? 1 : 0;
            worker->cross_group_victim_cursor = worker_index
                % scheduler->group_worker_counts[other_group];
        }
    }
#endif
}

static void literal_scheduler_finish(LiteralSchedulerWorker *worker) {
    atomic_store_explicit(&worker->scheduler->done.value, true, memory_order_release);
}

static void literal_scheduler_run(
    LiteralScheduler *scheduler, LiteralSchedulerTask *initial_task
) {
    if (initial_task->preferred_group >= scheduler->group_count) {
        fail_message("initial scheduler task has an invalid preferred topology group");
    }

    LiteralSchedulerWorker *initial_worker = NULL;
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        LiteralSchedulerWorker *worker = &scheduler->workers[worker_index];
        if (worker->group == initial_task->preferred_group) {
            initial_worker = worker;
            break;
        }
    }
    if (initial_worker == NULL) {
        fail_message("no worker matches the initial scheduler task");
    }
    push_work_deque(&initial_worker->deque, initial_task);

    pthread_t threads[example_maximum_workers];
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        int error_number = pthread_create(
            &threads[worker_index],
            NULL,
            run_scheduler_worker,
            &scheduler->workers[worker_index]
        );
        if (error_number != 0) {
            fail_errno("pthread_create", error_number);
        }
    }
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        int error_number = pthread_join(threads[worker_index], NULL);
        if (error_number != 0) {
            fail_errno("pthread_join", error_number);
        }
    }
}

static void literal_scheduler_destroy(LiteralScheduler *scheduler) {
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        destroy_work_deque(&scheduler->workers[worker_index].deque);
    }
#if !LITERAL_SINGLE_TOPOLOGY_GROUP
    for (size_t group = 0; group < scheduler->group_count; ++group) {
        destroy_injection_queue(&scheduler->group_injection[group]);
    }
#endif
}

typedef struct ExampleGraph ExampleGraph;

typedef struct {
    ExampleGraph *graph;
    size_t particle_index;
    LiteralSchedulerTask task;
} ExampleLeaf;

struct ExampleGraph {
    LiteralJoin join;
    uint64_t particles[2];
    unsigned int continuation_runs;
    LiteralSchedulerTask start;
    ExampleLeaf leaves[2];
    LiteralSchedulerTask continuation;
};

static LiteralSchedulerTask *run_example_continuation(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    ExampleGraph *graph = task->context;
    if (graph->particles[0] != 41 || graph->particles[1] != 42) {
        fail_message("the Join did not publish every Particle write");
    }
    ++graph->continuation_runs;
    literal_scheduler_finish(worker);
    return NULL;
}

static LiteralSchedulerTask *run_example_leaf(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    ExampleLeaf *leaf = task->context;
    ExampleGraph *graph = leaf->graph;
    graph->particles[leaf->particle_index] = 41 + leaf->particle_index;
    if (!literal_join_arrive(&graph->join)) {
        return NULL;
    }
#if LITERAL_SINGLE_TOPOLOGY_GROUP
    return run_example_continuation(worker, &graph->continuation);
#else
    if (literal_scheduler_can_continue(
            worker, &graph->continuation, true
        )) {
        return run_example_continuation(worker, &graph->continuation);
    }
    literal_scheduler_submit(worker, &graph->continuation);
    return NULL;
#endif
}

static LiteralSchedulerTask *run_example_start(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    ExampleGraph *graph = task->context;
    literal_scheduler_submit(worker, &graph->leaves[1].task);
    return run_example_leaf(worker, &graph->leaves[0].task);
}

static void initialize_example_graph(ExampleGraph *graph) {
    memset(graph, 0, sizeof(*graph));
    literal_join_initialize(&graph->join, 2);
    graph->start = (LiteralSchedulerTask){
        .function = run_example_start,
        .context = graph,
        .preferred_group = 0,
    };
    graph->continuation = (LiteralSchedulerTask){
        .function = run_example_continuation,
        .context = graph,
        .preferred_group = 0,
    };
    for (size_t particle_index = 0; particle_index < 2; ++particle_index) {
        graph->leaves[particle_index] = (ExampleLeaf){
            .graph = graph,
            .particle_index = particle_index,
            .task = {
                .function = run_example_leaf,
                .context = &graph->leaves[particle_index],
                .preferred_group = (uint16_t)particle_index,
            },
        };
    }
}

int main(void) {
    LiteralSchedulerConfig config;
    memset(&config, 0, sizeof(config));
    config.worker_count = 2;
    config.group_count = 2;
    config.group_ids[1] = 1;
    config.cross_group_poll_delay = 64;
    for (size_t worker_index = 0; worker_index < example_maximum_workers;
         ++worker_index) {
        config.processor_ids[worker_index] = -1;
    }

    LiteralScheduler scheduler;
    literal_scheduler_initialize(&scheduler, &config);
    ExampleGraph graph;
    initialize_example_graph(&graph);
    literal_scheduler_run(&scheduler, &graph.start);
    literal_scheduler_destroy(&scheduler);

    if (graph.continuation_runs != 1) {
        fail_message("the Join continuation did not run exactly once");
    }
    return EXIT_SUCCESS;
}
