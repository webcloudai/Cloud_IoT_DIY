/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';

class FlippableImage extends StatefulWidget {
  final String? imageName;
  final String? imageUrl;
  final String? displayText;
  final Widget? displayWidget;
  final double? imageScale;

  const FlippableImage(
      {Key? key,
      this.imageName,
      this.imageUrl,
      this.displayText,
      this.displayWidget,
      this.imageScale})
      : super(key: key);

  @override
  FlippableImageState createState() => FlippableImageState();
}

class FlippableImageState extends State<FlippableImage> {
  bool _showText = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (event) {
        if (!_showText) {
          setState(() {
            _showText = true;
          });
        }
      },
      onExit: (event) {
        if (_showText) {
          setState(() {
            _showText = false;
          });
        }
      },
      child: _showText
          ? widget.displayText != null
              ? Center(child: Text(widget.displayText!))
              : widget.displayWidget
          : widget.imageName != null
              ? Image.asset(widget.imageName!,
                  scale: widget.imageScale ?? 1.0, fit: BoxFit.contain)
              : Image.network(widget.imageUrl!),
    );
  }
}
