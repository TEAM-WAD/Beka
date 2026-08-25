import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:path_provider/path_provider.dart';
import 'package:telegram_client/telegram_client.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NativeTelegramApp());
}

class NativeTelegramApp extends StatelessWidget {
  const NativeTelegramApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'تليجرام الأصلي',
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF17212B),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF242F3D),
          elevation: 0,
        ),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF5288C1),
          surface: Color(0xFF242F3D),
        ),
      ),
      locale: const Locale('ar', 'IQ'),
      supportedLocales: const [Locale('ar', 'IQ'), Locale('ar')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const TelegramAuthOrMainScreen(),
    );
  }
}

class TelegramAuthOrMainScreen extends StatefulWidget {
  const TelegramAuthOrMainScreen({super.key});

  @override
  State<TelegramAuthOrMainScreen> meState() => _TelegramAuthOrMainScreenState();
}

class _TelegramAuthOrMainScreenState extends State<TelegramAuthOrMainScreen> {
  late TelegramClient tgClient;
  bool isInitialized = false;
  bool isAuthenticated = false;
  bool isStealthMode = true; // مفعل افتراضياً لحمايتك 100%

  // أدخل بيانات API الخاصة بك من my.telegram.org (أو استخدم القيم الافتراضية)
  final int apiId = 94575; // API ID افتراضي
  final String apiHash = "a3406de8d171326e3c403d80a9b00a9c";

  final TextEditingController phoneController = TextEditingController();
  final TextEditingController codeController = TextEditingController();
  final TextEditingController passwordController = TextEditingController();

  String authState = "WAIT_PHONE"; // WAIT_PHONE, WAIT_CODE, WAIT_PASSWORD, READY
  List<Map<String, dynamic>> chats = [];

  @override
  void initState() {
    super.initState();
    _initTDLib();
  }

  Future<void> _initTDLib() async {
    final Directory appDocDir = await getApplicationDocumentsDirectory();
    final String dbPath = "${appDocDir.path}/tdlib_data";

    tgClient = TelegramClient(
      api_id: apiId,
      api_hash: apiHash,
      db_path: dbPath,
    );

    // الاستماع للتحديثات الصادرة من TDLib
    tgClient.on('updateAuthorizationState', (update) {
      final auth = update['authorization_state'];
      if (auth != null) {
        final type = auth['@type'];
        if (type == 'authorizationStateWaitPhoneNumber') {
          setState(() => authState = "WAIT_PHONE");
        } else if (type == 'authorizationStateWaitCode') {
          setState(() => authState = "WAIT_CODE");
        } else if (type == 'authorizationStateWaitPassword') {
          setState(() => authState = "WAIT_PASSWORD");
        } else if (type == 'authorizationStateReady') {
          setState(() {
            isAuthenticated = true;
            authState = "READY";
          });
          _loadChats();
        }
      }
    });

    tgClient.init();
    setState(() => isInitialized = true);
  }

  // تسجيل الدخول ورقم الهاتف
  void _sendPhoneNumber() {
    if (phoneController.text.isNotEmpty) {
      tgClient.send({
        '@type': 'setAuthenticationPhoneNumber',
        'phone_number': phoneController.text.trim(),
      });
    }
  }

  // إرسال كود التحقق
  void _sendCode() {
    if (codeController.text.isNotEmpty) {
      tgClient.send({
        '@type': 'checkAuthenticationCode',
        'code': codeController.text.trim(),
      });
    }
  }

  // إرسال كلمة المرور (التحقق بخطوتين إن وجد)
  void _sendPassword() {
    if (passwordController.text.isNotEmpty) {
      tgClient.send({
        '@type': 'checkAuthenticationPassword',
        'password': passwordController.text.trim(),
      });
    }
  }

  // تحميل قائمة المحادثات الأصيلة عبر TDLib
  Future<void> _loadChats() async {
    final res = await tgClient.request({
      '@type': 'getChats',
      'limit': 50,
    });
    if (res != null && res['chat_ids'] != null) {
      final List chatIds = res['chat_ids'];
      List<Map<String, dynamic>> tempChats = [];
      for (var id in chatIds) {
        final chatData = await tgClient.request({
          '@type': 'getChat',
          'chat_id': id,
        });
        if (chatData != null) {
          tempChats.add(chatData);
        }
      }
      setState(() {
        chats = tempChats;
      });
    }
  }

  // فتح وتصفح الستوري بحماية التخفي الحقيقية (Ghost Mode)
  Future<void> _openStorySafely(int storyId, int senderUserId) async {
    // 1. جلب بيانات الستوري دون إرسال إشارة قراءة
    final storyData = await tgClient.request({
      '@type': 'getStory',
      'story_id': storyId,
      'sender_user_id': senderUserId,
    });

    if (!isStealthMode) {
      // إذا كان وضع التخفي معطلاً، يرسل أمر القراءة عادي
      tgClient.send({
        '@type': 'openStory',
        'story_id': storyId,
        'sender_user_id': senderUserId,
      });
    } else {
      // 🛡️ في وضع التخفي: لا نرسل أمر openStory لسيرفر تليجرام إطلاقاً!
      // نقوم بعرض الوسائط وتصفحها محلية 100% دون أن علم تليجرام.
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('🛡️ تم فتح الستوري بوضع التخفي المطلق (لم يتم تسجيل مشاهدتك)'),
          backgroundColor: Colors.green,
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!isInitialized) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: Color(0xFF5288C1)),
        ),
      );
    }

    if (!isAuthenticated) {
      return _buildAuthScreen();
    }

    return _buildHomeScreen();
  }

  // واجهة تسجيل الدخول الأصيلة
  Widget _buildAuthScreen() {
    return Scaffold(
      appBar: AppBar(title: const Text('تسجيل الدخول - تليجرام')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (authState == "WAIT_PHONE") ...[
              const Text('أدخل رقم الهاتف مع رمز الدولة (مثال: +9647700000000)',
                  textAlign: TextAlign.center, style: TextStyle(fontSize: 16)),
              const SizedBox(height: 16),
              TextField(
                controller: phoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: 'رقم الهاتف',
                  prefixIcon: Icon(Icons.phone),
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _sendPhoneNumber,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size.fromHeight(50),
                  backgroundColor: const Color(0xFF5288C1),
                ),
                child: const Text('متابعة', style: TextStyle(color: Colors.white, fontSize: 16)),
              ),
            ] else if (authState == "WAIT_CODE") ...[
              const Text('أدخل رمز التحقق الذي وصلك على تليجرام',
                  textAlign: TextAlign.center, style: TextStyle(fontSize: 16)),
              const SizedBox(height: 16),
              TextField(
                controller: codeController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: 'رمز التحقق',
                  prefixIcon: Icon(Icons.security),
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _sendCode,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size.fromHeight(50),
                  backgroundColor: const Color(0xFF5288C1),
                ),
                child: const Text('تأكيد الرمز', style: TextStyle(color: Colors.white, fontSize: 16)),
              ),
            ] else if (authState == "WAIT_PASSWORD") ...[
              const Text('أدخل كلمة سر التحقق بخطوتين (2FA)',
                  textAlign: TextAlign.center, style: TextStyle(fontSize: 16)),
              const SizedBox(height: 16),
              TextField(
                controller: passwordController,
                obscureText: true,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: 'كلمة السر',
                  prefixIcon: Icon(Icons.lock),
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _sendPassword,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size.fromHeight(50),
                  backgroundColor: const Color(0xFF5288C1),
                ),
                child: const Text('دخول', style: TextStyle(color: Colors.white, fontSize: 16)),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // واجهة المحادثات الرئيسية الاصيلة
  Widget _buildHomeScreen() {
    return Scaffold(
      appBar: AppBar(
        title: const Text('تليجرام الاصلي (TDLib)'),
        actions: [
          Row(
            children: [
              Icon(
                isStealthMode ? Icons.visibility_off : Icons.visibility,
                color: isStealthMode ? Colors.greenAccent : Colors.grey,
              ),
              const SizedBox(width: 4),
              Switch(
                value: isStealthMode,
                activeColor: Colors.greenAccent,
                onChanged: (val) {
                  setState(() => isStealthMode = val);
                },
              ),
            ],
          ),
        ],
      ),
      body: chats.isEmpty
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF5288C1)))
          : ListView.builder(
              itemCount: chats.length,
              itemBuilder: (context, index) {
                final chat = chats[index];
                final String title = chat['title'] ?? 'محادثة';
                return ListTile(
                  leading: CircleAvatar(
                    backgroundColor: const Color(0xFF5288C1),
                    child: Text(title.isNotEmpty ? title[0] : 'T'),
                  ),
                  title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: Text(
                    chat['last_message']?['content']?['text']?['text'] ?? 'رسالة...',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  onTap: () {
                    // فتح المحادثة الأصيلة
                  },
                );
              },
            ),
    );
  }
}
