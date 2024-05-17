/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';
import 'dashboard_page.dart';
import 'main_page.dart';
import 'authentication_provider.dart';
import 'account_page.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
// import 'redirect_to_html.dart';

class MyApp extends StatelessWidget {
  final Color customBackgroundColor = const Color.fromARGB(
      255, 67, 67, 67); //const Color.fromARGB(255, 249, 245, 204);
  final Color customForegroundColor =
      const Color.fromARGB(255, 218, 218, 218); //Colors.deepPurple;

  MyApp({
    Key? key,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      theme: ThemeData(
        primaryColor: customBackgroundColor,
        appBarTheme: AppBarTheme(
            color: customBackgroundColor,
            foregroundColor: customForegroundColor),
        buttonTheme: ButtonThemeData(
          buttonColor: customBackgroundColor,
          textTheme: ButtonTextTheme.primary,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
            style: ElevatedButton.styleFrom(
                backgroundColor: customBackgroundColor,
                foregroundColor: customForegroundColor,
                textStyle: const TextStyle(fontWeight: FontWeight.bold))
            // buttonColor: customBackgroundColor,
            // textTheme: ButtonTextTheme.primary,
            ),
      ),
      debugShowCheckedModeBanner: false,
      routerConfig: _router,
    );
  }

  late final GoRouter _router = GoRouter(
    routes: <GoRoute>[
      GoRoute(
        path: '/',
        name: "home",
        builder: (BuildContext context, GoRouterState state) =>
            const MainPage(),
      ),
      GoRoute(
        path: '/dashboard',
        name: "dashboard",
        builder: (BuildContext context, GoRouterState state) =>
            Consumer<AuthenticationProvider>(
                builder: (context, authProvider, child) {
          if (!authProvider.isAuthenticated) {
            return const MainPage();
          }
          return const DashboardPage();
        }),
      ),
      GoRoute(
        path: '/account',
        name: "account",
        builder: (BuildContext context, GoRouterState state) =>
            Consumer<AuthenticationProvider>(
                builder: (context, authProvider, child) {
          if (!authProvider.isAuthenticated) {
            return const MainPage();
          }
          return const AccountPage();
        }),
      ),
    ],
  );
}
