`timescale 1ns/1ps
`default_nettype none
module tb_glitcher;
    reg clk = 0;
    always #10 clk = ~clk; // 50 MHz
    reg rst_n = 0, uart_rx = 1;
    wire uart_tx, reset_gate, glitch_out;
    localparam integer BIT_CLKS = 50; // Simulation override: 1 Mbaud
    integer resets = 0, pulses = 0;
    time reset_start, release_time, pulse_start;
    reg have_release = 0;
    reg [7:0] received;
    integer i;
    glitcher #(.CLK_FREQ(50_000_000), .BAUD_RATE(1_000_000),
               .RESET_CYCLES(7)) dut (
        .clk(clk), .rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx),
        .reset_gate(reset_gate), .glitch_out(glitch_out)
    );

    always @(posedge reset_gate) if (rst_n) begin
        resets = resets + 1;
        reset_start = $time;
    end
    always @(negedge reset_gate) if (rst_n && resets > 0) begin
        if (($time - reset_start) != 7*20) $fatal(1, "RESET length incorrect");
        release_time = $time;
        have_release = 1;
    end
    always @(posedge glitch_out) if (rst_n) begin
        pulse_start = $time;
        pulses = pulses + 1;
        // The two outputs can change in the same simulation time slot.
        #1;
        if (!have_release) $fatal(1, "Pulse before reset release");
        if (resets == 1 && (pulse_start - release_time) != 100*20)
            $fatal(1, "First delay incorrect");
        if (resets == 2 && (pulse_start - release_time) != 0)
            $fatal(1, "Zero delay incorrect");
    end
    always @(negedge glitch_out) if (rst_n && pulses > 0) begin
        if (resets == 1 && ($time - pulse_start) != 10*20)
            $fatal(1, "First width incorrect");
        if (resets == 2 && ($time - pulse_start) != 1*20)
            $fatal(1, "Second width incorrect");
    end
    task send_byte(input [7:0] value);
        integer n;
        begin
            @(negedge clk); uart_rx = 0;
            repeat (BIT_CLKS) @(negedge clk);
            for (n = 0; n < 8; n = n + 1) begin
                uart_rx = value[n];
                repeat (BIT_CLKS) @(negedge clk);
            end
            uart_rx = 1;
            repeat (BIT_CLKS) @(negedge clk);
        end
    endtask
    task send_packet(input [15:0] delay_cycles, input [15:0] width_cycles);
        begin
            send_byte(8'hAA); send_byte(delay_cycles[15:8]);
            send_byte(delay_cycles[7:0]); send_byte(width_cycles[15:8]);
            send_byte(width_cycles[7:0]); send_byte(8'h01);
        end
    endtask
    task receive_byte(output [7:0] value);
        integer n;
        begin
            @(negedge uart_tx);
            repeat (BIT_CLKS + BIT_CLKS/2) @(negedge clk);
            for (n = 0; n < 8; n = n + 1) begin
                value[n] = uart_tx;
                repeat (BIT_CLKS) @(negedge clk);
            end
            if (uart_tx !== 1'b1) $fatal(1, "UART stop bit missing");
        end
    endtask
    initial begin
        #10_000_000 $fatal(1, "Test timeout");
    end
    initial begin
        repeat (5) @(negedge clk); rst_n = 1;
        send_byte(8'h42); // ignored garbage
        send_packet(16'd100, 16'd10);
        wait (pulses == 1);
        @(negedge glitch_out);
        receive_byte(received);
        if (received !== 8'hAA) $fatal(1, "Missing DONE header");
        receive_byte(received);
        if (received !== 8'h55) $fatal(1, "Missing DONE code");
        repeat (BIT_CLKS*12) @(negedge clk);
        if (pulses != 1 || resets != 1) $fatal(1, "Unexpected retrigger");
        // With zero delay the output can finish before send_packet returns.
        fork
            send_packet(16'd0, 16'd1);
            begin
                wait (pulses == 2);
                @(negedge glitch_out);
                receive_byte(received);
                if (received !== 8'hAA) $fatal(1, "Missing second header");
                receive_byte(received);
                if (received !== 8'h55) $fatal(1, "Missing second DONE");
            end
        join
        $display("PASS: UART RX/TX, RESET 7 cycles, delay 100/0 cycles, pulse 10/1 cycles, repeat start");
        $finish;
    end
endmodule
`default_nettype wire
