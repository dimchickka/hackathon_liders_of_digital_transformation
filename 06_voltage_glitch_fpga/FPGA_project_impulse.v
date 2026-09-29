`timescale 1ns/1ps
`default_nettype none

// ============================================================
// Compact glitcher for EPM240
//
// ВАЖНО:
// Автоматический RESET RP2040 УБРАН.
// reset_gate всегда находится в 0.
//
// PC -> FPGA:
//     AA D_H D_L W_H W_L 01
//
// D:
//     16-бит delay в тактах 50 МГц
//     1 такт = 20 нс
//
// W:
//     используется младший байт W_L
//     ширина импульса в тактах 50 МГц
//
// Последовательность:
//
//     команда 0x01
//          |
//          |---- delay ----|
//                           |-- glitch_out --|
//
// Никакого reset перед импульсом больше нет.
//
// FPGA -> PC:
//     из-за текущей логики TX фактический ответ = 55 AA
// ============================================================


module glitcher #(
    parameter integer CLK_FREQ = 50_000_000,
    parameter integer BAUD_RATE = 115_200
) (
    input  wire clk,
    input  wire uart_rx,

    output wire uart_tx,
    output wire reset_gate,
    output wire glitch_out
);


    // ========================================================
    // Внутренний стартовый RESET логики FPGA
    // ========================================================

    reg [1:0] startup = 2'b00;

    always @(posedge clk)
        startup <= {startup[0], 1'b1};

    wire internal_rst_n;

    assign internal_rst_n = startup[1];


    // ========================================================
    // Машина состояний
    // ========================================================

    localparam [2:0]
        ST_IDLE   = 3'd0,
        ST_WAIT   = 3'd1,
        ST_PULSE  = 3'd2,
        ST_TX_AA  = 3'd3,
        ST_TX_55  = 3'd4;


    reg [2:0] state;
    reg [2:0] byte_index;

    reg [15:0] delay_val;
    reg [15:0] count;

    reg [7:0] width_val;


    // ========================================================
    // UART RX
    // ========================================================

    wire [7:0] rx_data;
    wire       rx_valid;


    uart_rx_8n1 #(
        .CLK_FREQ(CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) u_rx (
        .clk(clk),
        .rst_n(internal_rst_n),
        .rx(uart_rx),

        .data_out(rx_data),
        .data_valid(rx_valid)
    );


    // ========================================================
    // UART TX
    // ========================================================

    reg  tx_send;
    wire tx_busy;

    wire [7:0] tx_data;

    assign tx_data =
        (state == ST_TX_55) ? 8'h55 : 8'hAA;


    uart_tx_8n1 #(
        .CLK_FREQ(CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) u_tx (
        .clk(clk),
        .rst_n(internal_rst_n),

        .data_in(tx_data),
        .send(tx_send),

        .tx(uart_tx),
        .busy(tx_busy)
    );


    // ========================================================
    // ВЫХОДЫ
    // ========================================================

    // --------------------------------------------------------
    // RESET RP2040 полностью отключён.
    //
    // Раньше здесь:
    //
    // assign reset_gate =
    //     internal_rst_n && (state == ST_RESET);
    //
    // Теперь RESET никогда не активируется.
    // --------------------------------------------------------

    assign reset_gate = 1'b0;


    // glitch_out активен только непосредственно
    // во время состояния ST_PULSE.

    assign glitch_out =
        internal_rst_n && (state == ST_PULSE);


    // ========================================================
    // Основная логика glitcher
    // ========================================================

    always @(posedge clk or negedge internal_rst_n) begin

        if (!internal_rst_n) begin

            state      <= ST_IDLE;
            byte_index <= 3'd0;

            delay_val  <= 16'd0;
            width_val  <= 8'd0;

            count      <= 16'd0;

            tx_send    <= 1'b0;

        end else begin

            // По умолчанию send = 0.
            // Для запуска UART TX он поднимается на один такт.
            tx_send <= 1'b0;


            case (state)

                // ====================================================
                // IDLE — принимаем пакет UART
                // ====================================================

                ST_IDLE: begin

                    if (rx_valid) begin

                        case (byte_index)

                            // ----------------------------------------
                            // BYTE 0
                            // Header 0xAA
                            // ----------------------------------------

                            3'd0: begin

                                if (rx_data == 8'hAA)
                                    byte_index <= 3'd1;
                                else
                                    byte_index <= 3'd0;

                            end


                            // ----------------------------------------
                            // BYTE 1
                            // Delay HIGH
                            // ----------------------------------------

                            3'd1: begin

                                delay_val[15:8] <= rx_data;
                                byte_index <= 3'd2;

                            end


                            // ----------------------------------------
                            // BYTE 2
                            // Delay LOW
                            // ----------------------------------------

                            3'd2: begin

                                delay_val[7:0] <= rx_data;
                                byte_index <= 3'd3;

                            end


                            // ----------------------------------------
                            // BYTE 3
                            // Width HIGH
                            //
                            // Сейчас не используется.
                            // ----------------------------------------

                            3'd3: begin

                                byte_index <= 3'd4;

                            end


                            // ----------------------------------------
                            // BYTE 4
                            // Width LOW
                            // ----------------------------------------

                            3'd4: begin

                                width_val <= rx_data;
                                byte_index <= 3'd5;

                            end


                            // ----------------------------------------
                            // BYTE 5
                            // COMMAND
                            // ----------------------------------------

                            3'd5: begin

                                byte_index <= 3'd0;

                                if (rx_data == 8'h01) begin

                                    // ================================
                                    // ВАЖНО:
                                    //
                                    // НИКАКОГО RESET ЗДЕСЬ БОЛЬШЕ НЕТ.
                                    //
                                    // Сразу начинаем отсчитывать delay.
                                    // ================================

                                    if (delay_val != 16'd0) begin

                                        count <= delay_val;
                                        state <= ST_WAIT;

                                    end

                                    else if (width_val != 8'd0) begin

                                        count <= {
                                            8'd0,
                                            width_val
                                        };

                                        state <= ST_PULSE;

                                    end

                                    else begin

                                        // И delay = 0,
                                        // и width = 0.
                                        //
                                        // Просто отвечаем ПК.

                                        state <= ST_TX_AA;

                                    end

                                end

                            end


                            default: begin

                                byte_index <= 3'd0;

                            end

                        endcase
                    end
                end


                // ====================================================
                // WAIT
                //
                // Отсчитываем delay.
                // ====================================================

                ST_WAIT: begin

                    if (count == 16'd1) begin

                        if (width_val != 8'd0) begin

                            count <= {
                                8'd0,
                                width_val
                            };

                            state <= ST_PULSE;

                        end

                        else begin

                            // width = 0
                            // Импульса не будет.

                            state <= ST_TX_AA;

                        end

                    end

                    else begin

                        count <= count - 16'd1;

                    end

                end


                // ====================================================
                // PULSE
                //
                // Пока мы здесь:
                //
                // glitch_out = 1
                //
                // Длительность:
                //
                // width_val * 20 нс
                //
                // при CLK = 50 МГц.
                // ====================================================

                ST_PULSE: begin

                    if (count == 16'd1) begin

                        state <= ST_TX_AA;

                    end

                    else begin

                        count <= count - 16'd1;

                    end

                end


                // ====================================================
                // TX первый байт
                // ====================================================

                ST_TX_AA: begin

                    if (!tx_busy && !tx_send) begin

                        tx_send <= 1'b1;
                        state <= ST_TX_55;

                    end

                end


                // ====================================================
                // TX второй байт
                // ====================================================

                ST_TX_55: begin

                    if (!tx_busy && !tx_send) begin

                        tx_send <= 1'b1;
                        state <= ST_IDLE;

                    end

                end


                // ====================================================
                // Защита
                // ====================================================

                default: begin

                    state <= ST_IDLE;
                    byte_index <= 3'd0;

                end

            endcase
        end
    end

endmodule



// ============================================================
// UART RX
// 8 data bits
// no parity
// 1 stop bit
// ============================================================

module uart_rx_8n1 #(
    parameter integer CLK_FREQ = 50_000_000,
    parameter integer BAUD_RATE = 115_200
) (
    input  wire clk,
    input  wire rst_n,
    input  wire rx,

    output reg [7:0] data_out,
    output reg       data_valid
);


    // ========================================================
    // UART timing
    // ========================================================

    localparam integer TICKS =
        (CLK_FREQ + BAUD_RATE / 2) / BAUD_RATE;

    localparam integer HALF_TICKS =
        TICKS / 2;

    localparam integer CW =
        (TICKS <= 2) ? 1 : $clog2(TICKS);


    localparam [CW-1:0] HALF_RELOAD =
        HALF_TICKS - 1;

    localparam [CW-1:0] BIT_RELOAD =
        TICKS - 1;


    // ========================================================
    // RX states
    // ========================================================

    localparam [1:0]
        RX_IDLE  = 2'd0,
        RX_START = 2'd1,
        RX_DATA  = 2'd2,
        RX_STOP  = 2'd3;


    // ========================================================
    // Registers
    // ========================================================

    reg rx_meta;
    reg rx_sync;

    reg [1:0] rx_state;

    reg [CW-1:0] timer;

    reg [2:0] bit_index;


    // ========================================================
    // RX logic
    // ========================================================

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            rx_meta <= 1'b1;
            rx_sync <= 1'b1;

            rx_state <= RX_IDLE;

            timer <= {CW{1'b0}};

            bit_index <= 3'd0;

            data_out <= 8'd0;
            data_valid <= 1'b0;

        end

        else begin

            // ------------------------------------------------
            // Двухтактный синхронизатор UART RX
            // ------------------------------------------------

            rx_meta <= rx;
            rx_sync <= rx_meta;


            // data_valid — импульс длительностью один clk
            data_valid <= 1'b0;


            case (rx_state)

                // ====================================================
                // Ждём стартовый бит
                // ====================================================

                RX_IDLE: begin

                    if (!rx_sync) begin

                        timer <= HALF_RELOAD;
                        rx_state <= RX_START;

                    end

                end


                // ====================================================
                // Проверяем середину START BIT
                // ====================================================

                RX_START: begin

                    if (timer == {CW{1'b0}}) begin

                        if (!rx_sync) begin

                            timer <= BIT_RELOAD;
                            bit_index <= 3'd0;

                            rx_state <= RX_DATA;

                        end

                        else begin

                            // Ложный старт

                            rx_state <= RX_IDLE;

                        end

                    end

                    else begin

                        timer <= timer - 1'b1;

                    end

                end


                // ====================================================
                // Принимаем 8 бит
                // ====================================================

                RX_DATA: begin

                    if (timer == {CW{1'b0}}) begin

                        data_out[bit_index] <= rx_sync;

                        timer <= BIT_RELOAD;

                        if (bit_index == 3'd7) begin

                            rx_state <= RX_STOP;

                        end

                        else begin

                            bit_index <= bit_index + 3'd1;

                        end

                    end

                    else begin

                        timer <= timer - 1'b1;

                    end

                end


                // ====================================================
                // STOP BIT
                // ====================================================

                RX_STOP: begin

                    if (timer == {CW{1'b0}}) begin

                        if (rx_sync)
                            data_valid <= 1'b1;

                        rx_state <= RX_IDLE;

                    end

                    else begin

                        timer <= timer - 1'b1;

                    end

                end


                default: begin

                    rx_state <= RX_IDLE;

                end

            endcase
        end
    end

endmodule



// ============================================================
// UART TX
// 8 data bits
// no parity
// 1 stop bit
// ============================================================

module uart_tx_8n1 #(
    parameter integer CLK_FREQ = 50_000_000,
    parameter integer BAUD_RATE = 115_200
) (
    input wire clk,
    input wire rst_n,

    input wire [7:0] data_in,
    input wire       send,

    output reg tx,
    output reg busy
);


    // ========================================================
    // UART timing
    // ========================================================

    localparam integer TICKS =
        (CLK_FREQ + BAUD_RATE / 2) / BAUD_RATE;

    localparam integer CW =
        (TICKS <= 2) ? 1 : $clog2(TICKS);

    localparam [CW-1:0] BIT_RELOAD =
        TICKS - 1;


    // ========================================================
    // TX states
    // ========================================================

    localparam [1:0]
        TX_IDLE  = 2'd0,
        TX_START = 2'd1,
        TX_DATA  = 2'd2,
        TX_STOP  = 2'd3;


    // ========================================================
    // Registers
    // ========================================================

    reg [1:0] tx_state;

    reg [CW-1:0] timer;

    reg [2:0] bit_index;

    reg [7:0] shift;


    // ========================================================
    // TX logic
    // ========================================================

    always @(posedge clk or negedge rst_n) begin

        if (!rst_n) begin

            tx <= 1'b1;
            busy <= 1'b0;

            tx_state <= TX_IDLE;

            timer <= {CW{1'b0}};

            bit_index <= 3'd0;

            shift <= 8'd0;

        end

        else begin

            case (tx_state)

                // ====================================================
                // IDLE
                // ====================================================

                TX_IDLE: begin

                    if (send) begin

                        shift <= data_in;

                        bit_index <= 3'd0;

                        timer <= BIT_RELOAD;

                        // START bit
                        tx <= 1'b0;

                        busy <= 1'b1;

                        tx_state <= TX_START;

                    end

                end


                // ====================================================
                // START BIT
                // ====================================================

                TX_START: begin

                    if (timer == {CW{1'b0}}) begin

                        tx <= shift[0];

                        timer <= BIT_RELOAD;

                        tx_state <= TX_DATA;

                    end

                    else begin

                        timer <= timer - 1'b1;

                    end

                end


                // ====================================================
                // DATA BITS
                // ====================================================

                TX_DATA: begin

                    if (timer == {CW{1'b0}}) begin

                        timer <= BIT_RELOAD;

                        if (bit_index == 3'd7) begin

                            // STOP BIT
                            tx <= 1'b1;

                            tx_state <= TX_STOP;

                        end

                        else begin

                            bit_index <= bit_index + 3'd1;

                            tx <= shift[
                                bit_index + 3'd1
                            ];

                        end

                    end

                    else begin

                        timer <= timer - 1'b1;

                    end

                end


                // ====================================================
                // STOP BIT
                // ====================================================

                TX_STOP: begin

                    if (timer == {CW{1'b0}}) begin

                        busy <= 1'b0;

                        tx_state <= TX_IDLE;

                    end

                    else begin

                        timer <= timer - 1'b1;

                    end

                end


                default: begin

                    tx_state <= TX_IDLE;
                    tx <= 1'b1;
                    busy <= 1'b0;

                end

            endcase
        end
    end

endmodule


`default_nettype wire