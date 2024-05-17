/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'authentication_provider.dart';
import 'custom_appbar.dart';
import 'package:url_launcher/url_launcher.dart';
import 'canvas_ecg.dart';

Future<void> simpleLaunchUrl(url) async {
  final Uri uri = Uri.parse(url);
  if (!await launchUrl(uri)) {
    throw 'Could not launch $uri';
  }
}

TextStyle mainStyle() {
  return const TextStyle(
      fontFamily: 'Helvetica Neue',
      fontSize: 18,
      color: Color(0xff707070),
      fontWeight: FontWeight.bold);
}

class MainPage extends StatelessWidget {
  const MainPage({
    Key? key,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) =>
      Consumer<AuthenticationProvider>(builder: (context, authProvider, child) {
        return Scaffold(
            appBar: const CustomAppBar(
              titleText: 'Cloud IoT DIY UI',
            ),
            body: Stack(alignment: Alignment.topCenter, children: [
              CustomPaint(size: Size.infinite, painter: EKGPainter()),
              Container(
                alignment: Alignment.center,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: <Widget>[
                    Column(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Image.asset("assets/00035-1352164018-01.png"),
                          Column(
                            mainAxisAlignment: MainAxisAlignment.spaceAround,
                            children: [
                              if (authProvider.role != null)
                                Column(
                                  children: [
                                    Text(
                                      'Your current role is',
                                      style: mainStyle(),
                                    ),
                                    Text(
                                      authProvider.role!,
                                      style: const TextStyle(
                                          fontFamily: 'Helvetica Neue',
                                          fontSize: 18,
                                          color: Color.fromARGB(255, 24, 1, 48),
                                          fontWeight: FontWeight.bold),
                                    ),
                                  ],
                                ),
                              if (authProvider.role == null)
                                Column(
                                  children: [
                                    Text(
                                      '', //'Please log in to continue.',
                                      style: mainStyle(),
                                    ),
                                    ElevatedButton(
                                      child: const Text('Log In'),
                                      onPressed: () {
                                        context
                                            .read<AuthenticationProvider>()
                                            .logIn();
                                      },
                                    ),
                                  ],
                                )
                              else
                                ElevatedButton(
                                  child: const Text('Log Out'),
                                  onPressed: () {
                                    context
                                        .read<AuthenticationProvider>()
                                        .logOut();
                                  },
                                ),
                            ],
                          ),
                        ]),
                    const Text("Copyright 2023"),
                  ],
                ),
              ),
            ]));
      });
}
