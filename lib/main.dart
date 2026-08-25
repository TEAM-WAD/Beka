import 'package:flutter/material.dart';
import 'package:telegram_client/telegram_client.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TelegramApp());
}

class TelegramApp extends StatelessWidget {
  const TelegramApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Telegram Native Custom',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF17212B),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF242F3D),
          elevation: 0,
        ),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF64B5F6),
          surface: Color(0xFF242F3D),
        ),
      ),
      home: const TelegramAuthOrMainScreen(),
    );
  }
}

class TelegramAuthOrMainScreen extends StatefulWidget {
  const TelegramAuthOrMainScreen({super.key});

  @override
  State<TelegramAuthOrMainScreen> createState() => _TelegramAuthOrMainScreenState();
}

class _TelegramAuthOrMainScreenState extends State<TelegramAuthOrMainScreen> {
  final Tdlib _tdlib = Tdlib();
  int _clientId = 0;
  
  bool _isLoading = true;
  bool _isAuthorized = false;
  String _authState = 'wait_parameters'; // wait_parameters, wait_phone, wait_code, ready
  
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _codeController = TextEditingController();
  final TextEditingController _apiIdController = TextEditingController();
  final TextEditingController _apiHashController = TextEditingController();

  List<Map<String, dynamic>> _chats = [];
  String _statusMessage = 'جاري التهيئة...';

  @override
  void initState() {
    super.initState();
    _initTdlib();
  }

  Future<void> _initTdlib() async {
    try {
      _clientId = _tdlib.createclient();
      
      _tdlib.on(_tdlib.event_update, (UpdateTelegramClientTdlib update) {
        if (update.client_id == _clientId && update.raw is Map) {
          _handleUpdate(Map<String, dynamic>.from(update.raw));
        }
      });

      setState(() {
        _isLoading = false;
        _statusMessage = 'جاهز للتسجيل';
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _statusMessage = 'خطأ في تهيئة TDLib: $e';
      });
    }
  }

  void _handleUpdate(Map<String, dynamic> update) {
    final type = update['@type'];
    if (type == 'updateAuthorizationState') {
      final authState = update['authorization_state'];
      if (authState != null && authState is Map) {
        final authType = authState['@type'];
        setState(() {
          if (authType == 'authorizationStateWaitTdlibParameters') {
            _authState = 'wait_parameters';
          } else if (authType == 'authorizationStateWaitPhoneNumber') {
            _authState = 'wait_phone';
          } else if (authType == 'authorizationStateWaitCode') {
            _authState = 'wait_code';
          } else if (authType == 'authorizationStateReady') {
            _isAuthorized = true;
            _authState = 'ready';
            _loadChats();
          }
        });
      }
    }
  }

  Future<void> _sendTdlibParameters() async {
    final apiId = int.tryParse(_apiIdController.text.trim()) ?? 0;
    final apiHash = _apiHashController.text.trim();

    if (apiId == 0 || apiHash.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('يرجى إدخال API ID و API Hash بشكل صحيح')),
      );
      return;
    }

    setState(() => _isLoading = true);

    await _tdlib.invoke(
      'setTdlibParameters',
      parameters: {
        'api_id': apiId,
        'api_hash': apiHash,
        'system_language_code': 'ar',
        'device_model': 'Android Mobile',
        'application_version': '1.0.0',
        'use_secret_chats': true,
        'use_message_database': true,
        'use_file_database': true,
      },
      clientId: _clientId,
    );

    setState(() => _isLoading = false);
  }

  Future<void> _sendPhoneNumber() async {
    final phone = _phoneController.text.trim();
    if (phone.isEmpty) return;

    setState(() => _isLoading = true);

    await _tdlib.invoke(
      'setAuthenticationPhoneNumber',
      parameters: {
        'phone_number': phone,
      },
      clientId: _clientId,
    );

    setState(() => _isLoading = false);
  }

  Future<void> _sendCode() async {
    final code = _codeController.text.trim();
    if (code.isEmpty) return;

    setState(() => _isLoading = true);

    await _tdlib.invoke(
      'checkAuthenticationCode',
      parameters: {
        'code': code,
      },
      clientId: _clientId,
    );

    setState(() => _isLoading = false);
  }

  Future<void> _loadChats() async {
    setState(() => _isLoading = true);

    final res = await _tdlib.invoke(
      'getChats',
      parameters: {
        'limit': 30,
      },
      clientId: _clientId,
    );

    if (res is Map && res['chat_ids'] is List) {
      final List chatIds = res['chat_ids'];
      List<Map<String, dynamic>> loadedChats = [];
      for (var id in chatIds) {
        final chatData = await _tdlib.invoke(
          'getChat',
          parameters: {'chat_id': id},
          clientId: _clientId,
        );
        if (chatData is Map) {
          loadedChats.add(Map<String, dynamic>.from(chatData));
        }
      }
      setState(() {
        _chats = loadedChats;
      });
    }

    setState(() => _isLoading = false);
  }

  /// مشاهدة الاستوري بدون إرسال إشعار للمرسل (وضع التخفي Stealth Mode)
  Future<void> _viewStoryStealth(int chatId, int storyId) async {
    // نجلب بيانات وسائط الاستوري دون استدعاء openStory أو viewMessages
    final storyData = await _tdlib.invoke(
      'getStory',
      parameters: {
        'story_sender_chat_id': chatId,
        'story_id': storyId,
      },
      clientId: _clientId,
    );

    if (mounted) {
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          backgroundColor: const Color(0xFF242F3D),
          title: const Text('مشاهدة الاستوري (مخفي)', style: TextStyle(color: Colors.white)),
          content: Text(
            'تم جلب الاستوري بنجاح دون إرسال إشعار مشاهدة للسيرفر!\n\n$storyData',
            style: const TextStyle(color: Colors.white70),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('إغلاق'),
            ),
          ],
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 16),
              Text(_statusMessage, style: const TextStyle(color: Colors.white70)),
            ],
          ),
        ),
      );
    }

    if (!_isAuthorized) {
      return Scaffold(
        appBar: AppBar(title: const Text('تسجيل الدخول - تليجرام الأصلي')),
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 20),
              TextField(
                controller: _apiIdController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'API ID',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _apiHashController,
                decoration: const InputDecoration(
                  labelText: 'API Hash',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: _sendTdlibParameters,
                child: const Text('1. إرسال مفاتيح API'),
              ),
              const Divider(height: 40),
              if (_authState == 'wait_phone' || _authState == 'wait_parameters') ...[
                TextField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    labelText: 'رقم الهاتف (مع الرمز الدولي)',
                    hintText: '+964xxxxxxxxx',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _sendPhoneNumber,
                  style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                  child: const Text('2. إرسال رقم الهاتف'),
                ),
              ],
              if (_authState == 'wait_code') ...[
                TextField(
                  controller: _codeController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'رمز التحقق (SMS Code)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _sendCode,
                  style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                  child: const Text('3. تأكيد الرمز ودخول التطبيق'),
                ),
              ],
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('محادثات تليجرام (وضع التخفي)'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadChats,
          ),
        ],
      ),
      body: _chats.isEmpty
          ? const Center(child: Text('لا توجد محادثات محملة حالياً'))
          : ListView.builder(
              itemCount: _chats.length,
              itemBuilder: (context, index) {
                final chat = _chats[index];
                final title = chat['title'] ?? 'محادثة ${chat['id']}';
                return ListTile(
                  leading: const CircleAvatar(
                    backgroundColor: Color(0xFF64B5F6),
                    child: Icon(Icons.person, color: Colors.white),
                  ),
                  title: Text(title, style: const TextStyle(color: Colors.white)),
                  subtitle: Text('ID: ${chat['id']}', style: const TextStyle(color: Colors.grey)),
                  trailing: IconButton(
                    icon: const Icon(Icons.visibility_off, color: Colors.lightBlueAccent),
                    tooltip: 'مشاهدة الاستوري بدون علم صاحبها',
                    onPressed: () => _viewStoryStealth(chat['id'], 1),
                  ),
                );
              },
            ),
    );
  }
}
