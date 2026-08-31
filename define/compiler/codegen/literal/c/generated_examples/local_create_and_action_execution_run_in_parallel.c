static unsigned char test_particle;
static unsigned char other_trigger_particle;
static unsigned char other_item_particle;
static unsigned char local_item_particle;

static void action_other(void) {
    other_item_particle = 1;
    other_item_particle = 0;
}

static void action_test(void) {
    other_trigger_particle = 1;
    action_other();
    other_trigger_particle = 0;

    local_item_particle = 1;
    local_item_particle = 0;
}

int main(void) {
    test_particle = 1;
    action_test();
    return 0;
}
