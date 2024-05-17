/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';
import 'dart:math';

class EKGPainter extends CustomPainter {
  final double strokeWidth;
  final Color color;
  final int lines;

  EKGPainter({
    this.strokeWidth = 2,
    this.color = const Color.fromARGB(255, 184, 183, 183), //245, 187, 183),
    this.lines = 3,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final onePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    final segmentWidth = size.width / 70;

    for (int i = 0; i < lines; i++) {
      final path = Path();
      final startY = (size.height / lines) * i + size.height / (lines * 2);
      double startX = 0;

      while (startX < size.width) {
        // P wave
        path.moveTo(startX, startY);
        path.quadraticBezierTo(startX + segmentWidth * 0.5, startY - 20,
            startX + segmentWidth, startY);

        // QRS Complex
        path.lineTo(startX + segmentWidth * 1.5, startY);
        path.quadraticBezierTo(
            startX + segmentWidth * 1.75,
            startY + 28 + 4 * Random().nextDouble(),
            startX + segmentWidth * 2,
            startY - 40 - 40 * Random().nextDouble());
        path.quadraticBezierTo(
            startX + segmentWidth * 2.25,
            startY + 28 + 4 * Random().nextDouble(),
            startX + segmentWidth * 3,
            startY);

        // T wave
        path.lineTo(startX + segmentWidth * 3.5, startY);
        path.quadraticBezierTo(startX + segmentWidth * 4.5, startY - 30,
            startX + segmentWidth * 5, startY);

        startX += segmentWidth * 5;
        canvas.drawPath(path, onePaint);
      }
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => false;
}
