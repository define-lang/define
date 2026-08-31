static unsigned char test_particle;
static unsigned char box_particle;
static unsigned char box_position_a_particle;
static unsigned char box_position_b_particle;

static void action_test(void) {
    box_particle = 1;

    box_position_a_particle = 1;
    box_position_a_particle = 0;

    box_position_b_particle = 1;
    box_position_b_particle = 0;

    box_particle = 0;
}

int main(void) {
    test_particle = 1;
    action_test();
    return 0;
}
